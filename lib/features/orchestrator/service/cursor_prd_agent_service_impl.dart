import 'dart:async';
import 'dart:convert';

import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/cursor_connection_failure.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/cloud_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_context.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_stream_event.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_key.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/cursor_credential_store_service.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/cursor_prd_agent_service.dart';
import 'package:pulse_ai/features/orchestrator/service/cursor_cloud_agent_http_client.dart';
import 'package:pulse_ai/features/orchestrator/service/cursor_cloud_run_id_codec.dart';
import 'package:pulse_ai/features/orchestrator/service/cursor_cloud_run_status_mapper.dart';
import 'package:pulse_ai/features/orchestrator/service/cursor_prd_agent_config.dart';
import 'package:pulse_ai/features/orchestrator/service/cursor_run_sse_parser.dart';
import 'package:pulse_ai/features/orchestrator/service/transient_http_retry.dart';
import 'package:uuid/uuid.dart';

final class CursorPrdAgentServiceImpl implements CursorPrdAgentService {
  CursorPrdAgentServiceImpl({
    required CursorCredentialStoreService credentialStore,
    required CursorCloudAgentHttpClient httpClient,
    CursorRunSseParser? sseParser,
    CursorCloudRunStatusMapper? statusMapper,
    TransientHttpRetry? retryPolicy,
    TransientHttpRetry? cancelRetryPolicy,
    Uuid? uuid,
  }) : _credentialStore = credentialStore,
       _httpClient = httpClient,
       _sseParser = sseParser ?? const CursorRunSseParser(),
       _statusMapper = statusMapper ?? const CursorCloudRunStatusMapper(),
       _retryPolicy = retryPolicy ?? const TransientHttpRetry(),
       _cancelRetryPolicyOverride = cancelRetryPolicy,
       _uuid = uuid ?? const Uuid();

  static const TransientHttpRetry _defaultCancelRetryPolicy =
      TransientHttpRetry(maxAttempts: 1);

  final CursorCredentialStoreService _credentialStore;
  final CursorCloudAgentHttpClient _httpClient;
  final CursorRunSseParser _sseParser;
  final CursorCloudRunStatusMapper _statusMapper;
  final TransientHttpRetry _retryPolicy;
  final TransientHttpRetry? _cancelRetryPolicyOverride;
  final Uuid _uuid;

  TransientHttpRetry get _cancelRetryPolicy =>
      _cancelRetryPolicyOverride ?? _defaultCancelRetryPolicy;

  @override
  Future<Either<Failure, void>> preflight() async {
    final String? credential = await _credentialStore.read();
    if (credential == null || credential.trim().isEmpty) {
      return left(const CursorConnectionFailure.missingCredential());
    }
    return preflightCredential(credential);
  }

  @override
  Future<Either<Failure, void>> preflightCredential(String apiKey) async {
    if (apiKey.trim().isEmpty) {
      return left(const CursorConnectionFailure.missingCredential());
    }

    try {
      final CursorHttpResponse response = await _retryPolicy.execute(
        () => _httpClient.get('/v1/me', credential: apiKey),
      );
      return _mapPreflightResponse(response);
    } on Object {
      return left(const CursorConnectionFailure.network());
    }
  }

  Either<Failure, void> _mapPreflightResponse(CursorHttpResponse response) {
    if (response.statusCode == 401) {
      return left(const CursorConnectionFailure.unauthorized());
    }
    if (response.statusCode >= 500) {
      return left(const CursorConnectionFailure.network());
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      return left(const CursorConnectionFailure.unknown());
    }
    return right(null);
  }

  @override
  Future<PrdRunEntity> startRun(PrdRunContext context) async {
    final String body = jsonEncode(<String, Object>{
      'prompt': <String, String>{'text': context.composedPrompt},
      'model': <String, String>{'id': CursorPrdAgentConfig.defaultModelId},
      'env': <String, String>{'type': 'machine', 'name': context.machineName},
    });

    final CursorHttpResponse response = await _retryPolicy.execute(
      () => _httpClient.post('/v1/agents', body: body),
    );

    if (response.statusCode == 401) {
      throw const PrdRunOperationException(
        CursorConnectionFailure.unauthorized(),
      );
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw const PrdRunOperationException(PrdRunFailure.cloudRunFailed());
    }

    final Map<String, dynamic>? decoded =
        jsonDecode(response.body) as Map<String, dynamic>?;
    final String? agentId = _readId(decoded, key: 'agent');
    final String? runId = _readId(decoded, key: 'run');
    if (agentId == null || runId == null) {
      throw const PrdRunOperationException(PrdRunFailure.cloudRunFailed());
    }

    final DateTime startedAt = DateTime.now().toUtc();
    return PrdRunEntity(
      id: _uuid.v4(),
      workflowKey: WorkflowKey.compose(
        projectId: context.projectId,
        slug: context.slug,
      ),
      cloudRunId: CursorCloudRunIdCodec.encode(agentId: agentId, runId: runId),
      status: PrdRunStatus.queued,
      supersedesRunId: context.supersedesRunId,
      feedback: context.feedback,
      startedAt: startedAt,
    );
  }

  String? _readId(Map<String, dynamic>? decoded, {required String key}) {
    final Object? container = decoded?[key];
    if (container is! Map<String, dynamic>) {
      return null;
    }
    final Object? id = container['id'];
    return id is String && id.isNotEmpty ? id : null;
  }

  @override
  Stream<PrdStreamEvent> watchRun(String cloudRunId) async* {
    final ({String agentId, String runId})? ids = CursorCloudRunIdCodec.decode(
      cloudRunId,
    );
    if (ids == null) {
      throw const PrdRunOperationException(PrdRunFailure.cloudRunNotFound());
    }

    final DateTime startedAt = DateTime.now().toUtc();
    final List<String> block = <String>[];
    int nextSequence = 0;

    try {
      await for (final String line in _httpClient.getSseLines(
        '/v1/agents/${ids.agentId}/runs/${ids.runId}/stream',
      )) {
        block.add(line);
        if (line.isEmpty) {
          for (final PrdStreamEvent event in _sseParser.parseLines(
            cloudRunId: cloudRunId,
            lines: block,
            startedAt: startedAt,
          )) {
            nextSequence++;
            yield PrdStreamEvent(
              runId: event.runId,
              eventType: event.eventType,
              sequence: nextSequence,
              timestamp: startedAt.add(Duration(milliseconds: nextSequence)),
              payloadSummary: event.payloadSummary,
            );
          }
          block.clear();
        }
      }

      if (block.isNotEmpty) {
        for (final PrdStreamEvent event in _sseParser.parseLines(
          cloudRunId: cloudRunId,
          lines: block,
          startedAt: startedAt,
        )) {
          nextSequence++;
          yield PrdStreamEvent(
            runId: event.runId,
            eventType: event.eventType,
            sequence: nextSequence,
            timestamp: startedAt.add(Duration(milliseconds: nextSequence)),
            payloadSummary: event.payloadSummary,
          );
        }
      }
    } on Object {
      throw const PrdRunOperationException(PrdRunFailure.streamUnavailable());
    }
  }

  @override
  Future<void> cancelRun(String cloudRunId) async {
    final ({String agentId, String runId})? ids = CursorCloudRunIdCodec.decode(
      cloudRunId,
    );
    if (ids == null) {
      throw const PrdRunOperationException(PrdRunFailure.cloudRunNotFound());
    }

    final CursorHttpResponse response = await _cancelRetryPolicy.execute(
      () => _httpClient.post(
        '/v1/agents/${ids.agentId}/runs/${ids.runId}/cancel',
      ),
    );

    if (response.statusCode == 401) {
      throw const PrdRunOperationException(
        CursorConnectionFailure.unauthorized(),
      );
    }
    if (response.statusCode == 404) {
      throw const PrdRunOperationException(PrdRunFailure.cloudRunNotFound());
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw const PrdRunOperationException(PrdRunFailure.cloudRunFailed());
    }
  }

  @override
  Future<Either<Failure, CloudRunStatus>> fetchRunStatus(
    String cloudRunId,
  ) async {
    final ({String agentId, String runId})? ids = CursorCloudRunIdCodec.decode(
      cloudRunId,
    );
    if (ids == null) {
      return left(const PrdRunFailure.cloudRunNotFound());
    }

    try {
      final CursorHttpResponse response = await _retryPolicy.execute(
        () => _httpClient.get('/v1/agents/${ids.agentId}/runs/${ids.runId}'),
      );
      return _mapFetchRunStatusResponse(response);
    } on Object {
      return left(const CursorConnectionFailure.network());
    }
  }

  Either<Failure, CloudRunStatus> _mapFetchRunStatusResponse(
    CursorHttpResponse response,
  ) {
    if (response.statusCode == 401) {
      return left(const CursorConnectionFailure.unauthorized());
    }
    if (response.statusCode == 404) {
      return left(const PrdRunFailure.cloudRunNotFound());
    }
    if (response.statusCode >= 500) {
      return left(const CursorConnectionFailure.network());
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      return left(const PrdRunFailure.cloudRunFailed());
    }

    final Map<String, dynamic>? decoded =
        jsonDecode(response.body) as Map<String, dynamic>?;
    final Object? statusValue = decoded?['status'];
    if (statusValue is! String || statusValue.isEmpty) {
      return left(const PrdRunFailure.cloudRunFailed());
    }

    final PrdRunStatus? mapped = _statusMapper.mapCloudStatus(statusValue);
    if (mapped == null) {
      return left(const PrdRunFailure.cloudRunFailed());
    }

    return right(CloudRunStatus(mappedPrdRunStatus: mapped));
  }
}
