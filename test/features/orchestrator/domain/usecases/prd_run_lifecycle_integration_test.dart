import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:path/path.dart' as p;
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/data/hive/orchestrator_hive_boxes.dart';
import 'package:pulse_ai/features/orchestrator/data/repositories/artifact_repository_impl.dart';
import 'package:pulse_ai/features/orchestrator/data/repositories/prd_run_repository_impl.dart';
import 'package:pulse_ai/features/orchestrator/data/repositories/workflow_repository_impl.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_key.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/complete_prd_agent_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/service/filesystem_artifact_service_impl.dart';

import '../../data/hive/orchestrator_hive_test_helper.dart';
import 'fake_cursor_prd_agent_service.dart';

void main() {
  group('PRD run lifecycle integration', () {
    late Directory tempRoot;
    late Directory workflowsRoot;
    late OrchestratorHiveBoxes boxes;
    late PrdRunRepositoryImpl prdRunRepository;
    late WorkflowRepositoryImpl workflowRepository;
    late ArtifactRepositoryImpl artifactRepository;

    const String projectId = '550e8400-e29b-41d4-a716-446655440000';
    const String slug = 'payments-api';

    setUpAll(() async {
      await OrchestratorHiveTestHelper.setUpHive();
    });

    tearDownAll(() async {
      await OrchestratorHiveTestHelper.tearDownHive();
    });

    setUp(() async {
      tempRoot = await Directory.systemTemp.createTemp(
        'pulse_prd_lifecycle_integration_',
      );
      workflowsRoot = Directory(p.join(tempRoot.path, 'pulse', 'workflows'));
      await workflowsRoot.create(recursive: true);

      boxes = await OrchestratorHiveTestHelper.openBoxes();
      prdRunRepository = PrdRunRepositoryImpl(boxes: boxes);
      workflowRepository = WorkflowRepositoryImpl(boxes: boxes);
      artifactRepository = ArtifactRepositoryImpl(
        artifactPersistenceService: FilesystemArtifactServiceImpl(
          workflowsRoot: workflowsRoot,
        ),
      );
    });

    tearDown(() async {
      await boxes.workflows.close();
      await boxes.prdRuns.close();
      await boxes.prdApprovals.close();
      await boxes.streamEvents.close();
      if (tempRoot.existsSync()) {
        tempRoot.deleteSync(recursive: true);
      }
    });

    test(
      'complete run leaves prd.md bytes matching agent output on disk',
      () async {
        final Either<Failure, WorkflowEntity> workflowResult =
            await workflowRepository.create(
              projectId: projectId,
              slug: slug,
              branchName: 'main',
            );
        expect(workflowResult.isRight(), isTrue);

        final Either<Failure, PrdRunEntity> runResult = await prdRunRepository
            .createRun(
              workflowKey: WorkflowKey.compose(
                projectId: projectId,
                slug: slug,
              ),
              status: PrdRunStatus.running,
            );
        final String runId = runResult.getRight().toNullable()!.id;

        final CompletePrdAgentRunUseCase useCase = CompletePrdAgentRunUseCase(
          prdRunRepository: prdRunRepository,
          workflowRepository: workflowRepository,
          artifactRepository: artifactRepository,
          clock: () => DateTime.utc(2026, 5, 21, 15),
        );

        final Either<Failure, PrdRunEntity> completeResult = await useCase(
          runId: runId,
          projectId: projectId,
          slug: slug,
          output: FakeCursorPrdAgentServiceForLifecycle.sampleCompletionOutput,
        );
        expect(completeResult.isRight(), isTrue);

        final File prdFile = File(
          p.join(workflowsRoot.path, projectId, slug, 'prd.md'),
        );
        expect(prdFile.existsSync(), isTrue);
        expect(
          prdFile.readAsStringSync(),
          FakeCursorPrdAgentServiceForLifecycle.samplePrdMarkdown,
        );
      },
    );
  });
}
