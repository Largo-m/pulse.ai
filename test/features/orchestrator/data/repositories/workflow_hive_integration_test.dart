import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/data/hive/orchestrator_hive_boxes.dart';
import 'package:pulse_ai/features/orchestrator/data/repositories/prd_run_repository_impl.dart';
import 'package:pulse_ai/features/orchestrator/data/repositories/workflow_repository_impl.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import '../hive/orchestrator_hive_test_helper.dart';

void main() {
  group('Workflow and PrdRun Hive integration', () {
    late OrchestratorHiveBoxes boxes;

    const String projectId = '550e8400-e29b-41d4-a716-446655440000';

    setUpAll(() async {
      await OrchestratorHiveTestHelper.setUpHive();
    });

    tearDownAll(() async {
      await OrchestratorHiveTestHelper.tearDownHive();
    });

    setUp(() async {
      boxes = await OrchestratorHiveTestHelper.openBoxes();
    });

    tearDown(() async {
      await boxes.workflows.clear();
      await boxes.prdRuns.clear();
      await boxes.prdApprovals.clear();
      await boxes.streamEvents.clear();
      await boxes.workflows.close();
      await boxes.prdRuns.close();
      await boxes.prdApprovals.close();
      await boxes.streamEvents.close();
    });

    test(
      'index-only workflow CRUD persists in Hive without filesystem store',
      () async {
        final WorkflowRepositoryImpl workflowRepository =
            WorkflowRepositoryImpl(boxes: boxes);
        final PrdRunRepositoryImpl prdRunRepository = PrdRunRepositoryImpl(
          boxes: boxes,
        );

        final Either<Failure, WorkflowEntity> createResult =
            await workflowRepository.create(
              projectId: projectId,
              slug: 'index-only',
              branchName: 'main',
              directive: 'Build payments PRD',
            );
        expect(createResult.isRight(), isTrue);

        final WorkflowEntity? found = await workflowRepository.findBySlug(
          projectId: projectId,
          slug: 'index-only',
        );
        expect(found?.directive, 'Build payments PRD');

        final Either<Failure, PrdRunEntity> runResult = await prdRunRepository
            .createRun(
              workflowKey: found!.workflowKey,
              status: PrdRunStatus.queued,
            );
        expect(runResult.isRight(), isTrue);
        expect(boxes.prdRuns.length, 1);
      },
    );
  });
}
