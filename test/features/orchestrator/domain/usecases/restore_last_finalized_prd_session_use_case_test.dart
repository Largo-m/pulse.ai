import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_persistence_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/restore_prd_session_request.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/restore_prd_session_result.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_key.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/fakes/fake_prd_run_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/restore_last_finalized_prd_session_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_conversation_message_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_stream_buffer_policy.dart';

void main() {
  group('RestoreLastFinalizedPrdSessionUseCase', () {
    const String projectId = 'project-1';
    const String slug = 'agent-a';
    final String workflowKeyA = WorkflowKey.compose(
      projectId: projectId,
      slug: slug,
    );
    final String workflowKeyB = WorkflowKey.compose(
      projectId: projectId,
      slug: 'agent-b',
    );
    final DateTime baseTime = DateTime.utc(2026, 5, 22, 12);

    late FakePrdRunRepository prdRunRepository;
    late RestoreLastFinalizedPrdSessionUseCase useCase;

    RestorePrdSessionRequest requestFor(String workflowKey) {
      return RestorePrdSessionRequest(
        workflowKey: workflowKey,
        workflowDirective: 'Diretiva do workflow',
      );
    }

    Future<PrdRunEntity> seedRun({
      required String workflowKey,
      required PrdRunStatus status,
      required DateTime startedAt,
      String? feedback,
    }) async {
      final Either<Failure, PrdRunEntity> created = await prdRunRepository
          .createRun(
            workflowKey: workflowKey,
            status: status,
            feedback: feedback,
          );
      final PrdRunEntity run = created.getRight().toNullable()!;
      final Either<Failure, PrdRunEntity> updated = await prdRunRepository
          .updateRun(
            PrdRunEntity(
              id: run.id,
              workflowKey: run.workflowKey,
              cloudRunId: run.cloudRunId,
              status: run.status,
              supersedesRunId: run.supersedesRunId,
              feedback: run.feedback,
              startedAt: startedAt,
              endedAt: run.endedAt,
            ),
          );
      return updated.getRight().toNullable()!;
    }

    Future<void> seedEvents({
      required String runId,
      required int count,
      String eventType = 'assistant',
    }) async {
      for (int sequence = 1; sequence <= count; sequence++) {
        await prdRunRepository.appendStreamEvent(
          runId: runId,
          eventType: eventType,
          payloadSummary: 'Evento $sequence',
          timestamp: baseTime.add(Duration(seconds: sequence)),
        );
      }
    }

    setUp(() {
      prdRunRepository = FakePrdRunRepository();
      useCase = RestoreLastFinalizedPrdSessionUseCase(
        prdRunRepository: prdRunRepository,
      );
    });

    test(
      'returns inProgressOnly when latest run is running and older run is completed',
      () async {
        await seedRun(
          workflowKey: workflowKeyA,
          status: PrdRunStatus.completed,
          startedAt: baseTime,
        );
        await seedRun(
          workflowKey: workflowKeyA,
          status: PrdRunStatus.running,
          startedAt: baseTime.add(const Duration(hours: 1)),
        );

        final Either<Failure, RestorePrdSessionResult> result = await useCase
            .call(requestFor(workflowKeyA));

        expect(result.isRight(), isTrue);
        final RestorePrdSessionResult value = result.getRight().toNullable()!;
        expect(value.outcome, RestorePrdSessionOutcome.inProgressOnly);
        expect(value.snapshot, isNull);
      },
    );

    test(
      'returns restored snapshot with 50 terminal lines and conversation when completed run has assistant events',
      () async {
        final PrdRunEntity run = await seedRun(
          workflowKey: workflowKeyA,
          status: PrdRunStatus.completed,
          startedAt: baseTime,
        );
        await seedEvents(runId: run.id, count: 50);

        final Either<Failure, RestorePrdSessionResult> result = await useCase
            .call(requestFor(workflowKeyA));

        expect(result.isRight(), isTrue);
        final RestorePrdSessionResult value = result.getRight().toNullable()!;
        expect(value.outcome, RestorePrdSessionOutcome.restored);
        final snapshot = value.snapshot!;
        expect(snapshot.runId, run.id);
        expect(snapshot.runStatus, PrdRunStatus.completed);
        expect(snapshot.terminalLines, hasLength(50));
        expect(snapshot.conversationMessages.length, greaterThan(0));
        expect(
          snapshot.conversationMessages.any(
            (PrdConversationMessageUiModel message) =>
                message.role == PrdConversationMessageRole.agent,
          ),
          isTrue,
        );
      },
    );

    test(
      'caps persisted events at maxInMemoryEvents for snapshot terminal lines',
      () async {
        final PrdRunEntity run = await seedRun(
          workflowKey: workflowKeyA,
          status: PrdRunStatus.completed,
          startedAt: baseTime,
        );
        await seedEvents(runId: run.id, count: 300);

        final Either<Failure, RestorePrdSessionResult> result = await useCase
            .call(requestFor(workflowKeyA));

        final snapshot = result.getRight().toNullable()!.snapshot!;
        expect(
          snapshot.terminalLines.length,
          PrdStreamBufferPolicy.maxInMemoryEvents,
        );
        expect(snapshot.terminalLines.first.sequence, 101);
        expect(snapshot.terminalLines.last.sequence, 300);
      },
    );

    test('returns empty when workflow has no runs', () async {
      final Either<Failure, RestorePrdSessionResult> result = await useCase
          .call(requestFor(workflowKeyA));

      expect(result.isRight(), isTrue);
      expect(
        result.getRight().toNullable()!.outcome,
        RestorePrdSessionOutcome.empty,
      );
    });

    test('returns inProgressOnly when all runs are non-terminal', () async {
      await seedRun(
        workflowKey: workflowKeyA,
        status: PrdRunStatus.queued,
        startedAt: baseTime,
      );
      await seedRun(
        workflowKey: workflowKeyA,
        status: PrdRunStatus.running,
        startedAt: baseTime.add(const Duration(hours: 1)),
      );

      final Either<Failure, RestorePrdSessionResult> result = await useCase
          .call(requestFor(workflowKeyA));

      expect(
        result.getRight().toNullable()!.outcome,
        RestorePrdSessionOutcome.inProgressOnly,
      );
    });

    test('propagates Left when listStreamEvents fails', () async {
      final PrdRunEntity run = await seedRun(
        workflowKey: workflowKeyA,
        status: PrdRunStatus.completed,
        startedAt: baseTime,
      );
      await seedEvents(runId: run.id, count: 1);
      prdRunRepository.listStreamEventsFailure =
          const PrdRunPersistenceFailure.hiveError();

      final Either<Failure, RestorePrdSessionResult> result = await useCase
          .call(requestFor(workflowKeyA));

      expect(result.isLeft(), isTrue);
      expect(result.getLeft().toNullable(), isA<PrdRunPersistenceFailure>());
    });

    test('propagates Left when listRunsForWorkflow fails', () async {
      prdRunRepository.listRunsForWorkflowFailure =
          const PrdRunPersistenceFailure.hiveError();

      final Either<Failure, RestorePrdSessionResult> result = await useCase
          .call(requestFor(workflowKeyA));

      expect(result.isLeft(), isTrue);
    });

    test('isolates snapshots by workflowKey', () async {
      final PrdRunEntity runA = await seedRun(
        workflowKey: workflowKeyA,
        status: PrdRunStatus.completed,
        startedAt: baseTime,
      );
      await seedEvents(runId: runA.id, count: 3, eventType: 'assistant');

      final PrdRunEntity runB = await seedRun(
        workflowKey: workflowKeyB,
        status: PrdRunStatus.completed,
        startedAt: baseTime,
      );
      await seedEvents(runId: runB.id, count: 2, eventType: 'status');

      final Either<Failure, RestorePrdSessionResult> resultA = await useCase
          .call(requestFor(workflowKeyA));
      final Either<Failure, RestorePrdSessionResult> resultB = await useCase
          .call(requestFor(workflowKeyB));

      expect(resultA.getRight().toNullable()!.snapshot!.runId, runA.id);
      expect(
        resultA.getRight().toNullable()!.snapshot!.terminalLines,
        hasLength(3),
      );
      expect(resultB.getRight().toNullable()!.snapshot!.runId, runB.id);
      expect(
        resultB.getRight().toNullable()!.snapshot!.terminalLines,
        hasLength(2),
      );
    });

    test(
      'integration: fake repo seed yields non-empty terminal lines and coherent conversation for same runId',
      () async {
        final PrdRunEntity run = await seedRun(
          workflowKey: workflowKeyA,
          status: PrdRunStatus.completed,
          startedAt: baseTime,
          feedback: 'Feedback do usuário',
        );
        await seedEvents(runId: run.id, count: 5, eventType: 'assistant');

        final Either<Failure, RestorePrdSessionResult> result = await useCase
            .call(requestFor(workflowKeyA));

        final snapshot = result.getRight().toNullable()!.snapshot!;
        expect(snapshot.terminalLines.length, greaterThan(0));
        expect(snapshot.conversationMessages.length, greaterThan(0));
        expect(
          snapshot.conversationMessages.every(
            (PrdConversationMessageUiModel message) =>
                message.role == PrdConversationMessageRole.user ||
                message.role == PrdConversationMessageRole.agent,
          ),
          isTrue,
        );
      },
    );
  });
}
