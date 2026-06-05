import 'package:fpdart/fpdart.dart';
import 'package:hive/hive.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_persistence_failure.dart';
import 'package:pulse_ai/features/orchestrator/data/hive/orchestrator_hive_boxes.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/stream_event_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/prd_run_repository.dart';
import 'package:uuid/uuid.dart';

final class PrdRunRepositoryImpl implements PrdRunRepository {
  PrdRunRepositoryImpl({required OrchestratorHiveBoxes boxes, Uuid? uuid})
    : _prdRunsBox = boxes.prdRuns,
      _prdApprovalsBox = boxes.prdApprovals,
      _streamEventsBox = boxes.streamEvents,
      _uuid = uuid ?? const Uuid();

  final Box<PrdRunEntity> _prdRunsBox;
  final Box<PrdApprovalEntity> _prdApprovalsBox;
  final Box<StreamEventEntity> _streamEventsBox;
  final Uuid _uuid;

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

    try {
      await _prdRunsBox.put(run.id, run);
      return right(run);
    } on Object {
      return left(const PrdRunPersistenceFailure.hiveError());
    }
  }

  @override
  Future<PrdRunEntity?> findRunById(String runId) {
    return Future<PrdRunEntity?>.value(_prdRunsBox.get(runId));
  }

  @override
  Future<Either<Failure, List<PrdRunEntity>>> listRunsForWorkflow(
    String workflowKey,
  ) async {
    try {
      final List<PrdRunEntity> runs =
          _prdRunsBox.values
              .where((PrdRunEntity run) => run.workflowKey == workflowKey)
              .toList(growable: false)
            ..sort(
              (PrdRunEntity a, PrdRunEntity b) =>
                  b.startedAt.compareTo(a.startedAt),
            );
      return right(runs);
    } on Object {
      return left(const PrdRunPersistenceFailure.hiveError());
    }
  }

  @override
  Future<Either<Failure, PrdRunEntity>> updateRun(PrdRunEntity run) async {
    if (!_prdRunsBox.containsKey(run.id)) {
      return left(const PrdRunPersistenceFailure.runNotFound());
    }

    try {
      await _prdRunsBox.put(run.id, run);
      return right(run);
    } on Object {
      return left(const PrdRunPersistenceFailure.hiveError());
    }
  }

  @override
  Future<Either<Failure, StreamEventEntity>> appendStreamEvent({
    required String runId,
    required String eventType,
    required String payloadSummary,
    required DateTime timestamp,
  }) async {
    if (!_prdRunsBox.containsKey(runId)) {
      return left(const PrdRunPersistenceFailure.runNotFound());
    }

    final int nextSequence = _nextStreamSequence(runId);
    final StreamEventEntity event = StreamEventEntity(
      runId: runId,
      sequence: nextSequence,
      eventType: eventType,
      payloadSummary: payloadSummary,
      timestamp: timestamp,
    );

    try {
      await _streamEventsBox.put(_streamEventKey(runId, nextSequence), event);
      return right(event);
    } on Object {
      return left(const PrdRunPersistenceFailure.hiveError());
    }
  }

  @override
  Future<Either<Failure, List<StreamEventEntity>>> listStreamEvents(
    String runId,
  ) async {
    try {
      final List<StreamEventEntity> events =
          _streamEventsBox.values
              .where((StreamEventEntity event) => event.runId == runId)
              .toList(growable: false)
            ..sort(
              (StreamEventEntity a, StreamEventEntity b) =>
                  a.sequence.compareTo(b.sequence),
            );
      return right(events);
    } on Object {
      return left(const PrdRunPersistenceFailure.hiveError());
    }
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

    try {
      await _prdApprovalsBox.put(workflowKey, approval);
      return right(approval);
    } on Object {
      return left(const PrdRunPersistenceFailure.hiveError());
    }
  }

  @override
  Future<PrdApprovalEntity?> findApproval(String workflowKey) {
    return Future<PrdApprovalEntity?>.value(_prdApprovalsBox.get(workflowKey));
  }

  int _nextStreamSequence(String runId) {
    int maxSequence = 0;
    for (final StreamEventEntity event in _streamEventsBox.values) {
      if (event.runId == runId && event.sequence > maxSequence) {
        maxSequence = event.sequence;
      }
    }
    return maxSequence + 1;
  }

  static String _streamEventKey(String runId, int sequence) {
    return '$runId:$sequence';
  }
}
