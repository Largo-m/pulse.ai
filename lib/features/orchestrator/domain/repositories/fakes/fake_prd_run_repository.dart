import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_persistence_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/stream_event_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/prd_run_repository.dart';
import 'package:uuid/uuid.dart';

final class FakePrdRunRepository implements PrdRunRepository {
  final Map<String, PrdRunEntity> _runs = <String, PrdRunEntity>{};
  final Map<String, PrdApprovalEntity> _approvals =
      <String, PrdApprovalEntity>{};
  final List<StreamEventEntity> _streamEvents = <StreamEventEntity>[];
  final Uuid _uuid = const Uuid();

  @override
  Future<Either<Failure, PrdRunEntity>> createRun({
    required String workflowKey,
    required PrdRunStatus status,
    String? cloudRunId,
    String? supersedesRunId,
    String? feedback,
  }) async {
    final PrdRunEntity run = PrdRunEntity(
      id: _uuid.v4(),
      workflowKey: workflowKey,
      cloudRunId: cloudRunId,
      status: status,
      supersedesRunId: supersedesRunId,
      feedback: feedback,
      startedAt: DateTime.now().toUtc(),
    );
    _runs[run.id] = run;
    return right(run);
  }

  @override
  Future<PrdRunEntity?> findRunById(String runId) async {
    return _runs[runId];
  }

  @override
  Future<Either<Failure, List<PrdRunEntity>>> listRunsForWorkflow(
    String workflowKey,
  ) async {
    final List<PrdRunEntity> runs = _runs.values
        .where((PrdRunEntity run) => run.workflowKey == workflowKey)
        .toList(growable: false);
    return right(runs);
  }

  @override
  Future<Either<Failure, PrdRunEntity>> updateRun(PrdRunEntity run) async {
    if (!_runs.containsKey(run.id)) {
      return left(const PrdRunPersistenceFailure.runNotFound());
    }
    _runs[run.id] = run;
    return right(run);
  }

  @override
  Future<Either<Failure, StreamEventEntity>> appendStreamEvent({
    required String runId,
    required String eventType,
    required String payloadSummary,
    required DateTime timestamp,
  }) async {
    if (!_runs.containsKey(runId)) {
      return left(const PrdRunPersistenceFailure.runNotFound());
    }

    final int nextSequence =
        _streamEvents
            .where((StreamEventEntity event) => event.runId == runId)
            .fold<int>(
              0,
              (int max, StreamEventEntity event) =>
                  event.sequence > max ? event.sequence : max,
            ) +
        1;

    final StreamEventEntity entity = StreamEventEntity(
      runId: runId,
      sequence: nextSequence,
      eventType: eventType,
      payloadSummary: payloadSummary,
      timestamp: timestamp,
    );
    _streamEvents.add(entity);
    return right(entity);
  }

  @override
  Future<Either<Failure, List<StreamEventEntity>>> listStreamEvents(
    String runId,
  ) async {
    final List<StreamEventEntity> events = _streamEvents
        .where((StreamEventEntity event) => event.runId == runId)
        .toList(growable: false);
    return right(events);
  }

  @override
  Future<Either<Failure, PrdApprovalEntity>> upsertApproval({
    required String workflowKey,
    required PrdApprovalStatus status,
    DateTime? approvedAt,
    DateTime? lastEditedAt,
    String? sourceRunId,
  }) async {
    final PrdApprovalEntity approval = PrdApprovalEntity(
      workflowKey: workflowKey,
      status: status,
      approvedAt: approvedAt,
      lastEditedAt: lastEditedAt,
      sourceRunId: sourceRunId,
    );
    _approvals[workflowKey] = approval;
    return right(approval);
  }

  @override
  Future<PrdApprovalEntity?> findApproval(String workflowKey) async {
    return _approvals[workflowKey];
  }
}
