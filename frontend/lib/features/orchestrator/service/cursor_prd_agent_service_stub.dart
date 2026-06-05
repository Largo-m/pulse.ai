import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/cursor_connection_failure.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/cloud_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_context.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_stream_event.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/cursor_credential_store_service.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/cursor_prd_agent_service.dart';

final class CursorPrdAgentServiceStub implements CursorPrdAgentService {
  CursorPrdAgentServiceStub({
    required CursorCredentialStoreService credentialStore,
  }) : _credentialStore = credentialStore;

  final CursorCredentialStoreService _credentialStore;

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
    return right(null);
  }

  @override
  Future<PrdRunEntity> startRun(PrdRunContext context) {
    throw UnimplementedError('CursorPrdAgentService.startRun is task_07');
  }

  @override
  Stream<PrdStreamEvent> watchRun(String cloudRunId) {
    throw UnimplementedError('CursorPrdAgentService.watchRun is task_07');
  }

  @override
  Future<void> cancelRun(String cloudRunId) {
    throw UnimplementedError('CursorPrdAgentService.cancelRun is task_07');
  }

  @override
  Future<Either<Failure, CloudRunStatus>> fetchRunStatus(String cloudRunId) {
    return Future<Either<Failure, CloudRunStatus>>.value(
      left(const PrdRunFailure.cloudRunFailed()),
    );
  }
}
