import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_request.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_stream_event.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_key.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/cursor_prd_agent_service.dart';
import 'package:pulse_ai/features/orchestrator/service/cursor_cloud_run_id_codec.dart';
import 'package:uuid/uuid.dart';

final class FakeCursorPrdAgentService implements CursorPrdAgentService {
  FakeCursorPrdAgentService({Uuid? uuid}) : _uuid = uuid ?? const Uuid();

  static const String fakeAgentId = 'bc-fake-agent';
  static const String fakeRunId = 'run-fake-001';
  static final String fakeCloudRunId = CursorCloudRunIdCodec.encode(
    agentId: fakeAgentId,
    runId: fakeRunId,
  );

  Either<Failure, void>? nextPreflightResult;
  int cancelRunCallCount = 0;
  String? lastCancelledCloudRunId;

  final Uuid _uuid;

  @override
  Future<Either<Failure, void>> preflight() async {
    return nextPreflightResult ?? right(null);
  }

  @override
  Future<PrdRunEntity> startRun(PrdRunRequest request) async {
    return PrdRunEntity(
      id: _uuid.v4(),
      workflowKey: WorkflowKey.compose(
        projectId: request.projectId,
        slug: request.slug,
      ),
      cloudRunId: CursorCloudRunIdCodec.encode(
        agentId: fakeAgentId,
        runId: fakeRunId,
      ),
      status: PrdRunStatus.queued,
      supersedesRunId: request.supersedesRunId,
      feedback: request.feedback,
      startedAt: DateTime.now().toUtc(),
    );
  }

  @override
  Stream<PrdStreamEvent> watchRun(String cloudRunId) async* {
    final DateTime startedAt = DateTime.now().toUtc();
    yield PrdStreamEvent(
      runId: cloudRunId,
      eventType: 'status',
      sequence: 1,
      timestamp: startedAt,
      payloadSummary: 'status=RUNNING',
    );
    yield PrdStreamEvent(
      runId: cloudRunId,
      eventType: 'assistant',
      sequence: 2,
      timestamp: startedAt.add(const Duration(milliseconds: 1)),
      payloadSummary: 'Generating PRD draft.',
    );
    yield PrdStreamEvent(
      runId: cloudRunId,
      eventType: 'done',
      sequence: 3,
      timestamp: startedAt.add(const Duration(milliseconds: 2)),
    );
  }

  @override
  Future<void> cancelRun(String cloudRunId) async {
    cancelRunCallCount++;
    lastCancelledCloudRunId = cloudRunId;
  }
}
