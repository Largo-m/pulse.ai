import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/stream_event_entity.dart';

abstract interface class PrdRunRepository {
  Future<Either<Failure, PrdRunEntity>> createRun({
    required String workflowKey,
    required PrdRunStatus status,
    String? cloudRunId,
    String? supersedesRunId,
    String? feedback,
  });

  Future<PrdRunEntity?> findRunById(String runId);

  Future<Either<Failure, List<PrdRunEntity>>> listRunsForWorkflow(
    String workflowKey,
  );

  Future<Either<Failure, PrdRunEntity>> updateRun(PrdRunEntity run);

  Future<Either<Failure, StreamEventEntity>> appendStreamEvent({
    required String runId,
    required String eventType,
    required String payloadSummary,
    required DateTime timestamp,
  });

  Future<Either<Failure, List<StreamEventEntity>>> listStreamEvents(
    String runId,
  );

  Future<Either<Failure, PrdApprovalEntity>> upsertApproval({
    required String workflowKey,
    required PrdApprovalStatus status,
    DateTime? approvedAt,
    DateTime? lastEditedAt,
    String? sourceRunId,
  });

  Future<PrdApprovalEntity?> findApproval(String workflowKey);
}
