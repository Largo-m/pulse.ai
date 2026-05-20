import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_persistence_failure.dart';
import 'package:pulse_ai/features/orchestrator/data/hive/orchestrator_hive_boxes.dart';
import 'package:pulse_ai/features/orchestrator/data/repositories/prd_run_repository_impl.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/stream_event_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/prd_run_repository.dart';
import '../hive/orchestrator_hive_test_helper.dart';

void main() {
  group('PrdRunRepositoryImpl', () {
    late OrchestratorHiveBoxes boxes;
    late PrdRunRepository repository;

    const String workflowKey =
        '550e8400-e29b-41d4-a716-446655440000::payments-api';

    setUpAll(() async {
      await OrchestratorHiveTestHelper.setUpHive();
    });

    tearDownAll(() async {
      await OrchestratorHiveTestHelper.tearDownHive();
    });

    setUp(() async {
      boxes = await OrchestratorHiveTestHelper.openBoxes();
      repository = PrdRunRepositoryImpl(boxes: boxes);
    });

    tearDown(() async {
      await boxes.streamEvents.clear();
      await boxes.prdRuns.clear();
      await boxes.prdApprovals.clear();
      await boxes.streamEvents.close();
      await boxes.prdRuns.close();
      await boxes.prdApprovals.close();
      await boxes.workflows.close();
    });

    test(
      'appendStreamEvent increments sequence monotonically per runId',
      () async {
        final Either<Failure, PrdRunEntity> runResult = await repository
            .createRun(workflowKey: workflowKey, status: PrdRunStatus.running);
        final PrdRunEntity run = runResult.getOrElse(
          (Failure _) => throw StateError('run missing'),
        );
        final String runId = run.id;

        final Either<Failure, StreamEventEntity> first = await repository
            .appendStreamEvent(
              runId: runId,
              eventType: 'log',
              payloadSummary: 'first',
              timestamp: DateTime.utc(2026, 5, 20, 10),
            );
        final Either<Failure, StreamEventEntity> second = await repository
            .appendStreamEvent(
              runId: runId,
              eventType: 'log',
              payloadSummary: 'second',
              timestamp: DateTime.utc(2026, 5, 20, 11),
            );

        expect(
          first.getOrElse((Failure _) => throw StateError('')).sequence,
          1,
        );
        expect(
          second.getOrElse((Failure _) => throw StateError('')).sequence,
          2,
        );
      },
    );

    test(
      'appendStreamEvent returns runNotFound when runId is unknown',
      () async {
        final Either<Failure, StreamEventEntity> result = await repository
            .appendStreamEvent(
              runId: 'missing-run',
              eventType: 'log',
              payloadSummary: 'summary',
              timestamp: DateTime.utc(2026, 5, 20),
            );

        expect(result.isLeft(), isTrue);
        expect(
          result.getLeft().toNullable(),
          isA<PrdRunPersistenceFailure>().having(
            (PrdRunPersistenceFailure failure) => failure.code,
            'code',
            PrdRunPersistenceFailureCode.runNotFound,
          ),
        );
      },
    );

    test('upsertApproval links approval metadata by workflowKey', () async {
      final Either<Failure, PrdApprovalEntity> upsertResult = await repository
          .upsertApproval(
            workflowKey: workflowKey,
            status: PrdApprovalStatus.pendingApproval,
            lastEditedAt: DateTime.utc(2026, 5, 20, 12),
            sourceRunId: 'run-1',
          );

      expect(upsertResult.isRight(), isTrue);

      final PrdApprovalEntity? found = await repository.findApproval(
        workflowKey,
      );
      expect(found?.status, PrdApprovalStatus.pendingApproval);
      expect(found?.sourceRunId, 'run-1');
    });
  });
}
