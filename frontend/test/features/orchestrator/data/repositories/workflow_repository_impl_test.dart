import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:path/path.dart' as p;
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/workflow_persistence_failure.dart';
import 'package:pulse_ai/features/orchestrator/data/hive/orchestrator_hive_boxes.dart';
import 'package:pulse_ai/features/orchestrator/data/repositories/workflow_repository_impl.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/workflow_repository.dart';
import 'package:pulse_ai/features/orchestrator/service/filesystem_artifact_service_impl.dart';
import '../hive/orchestrator_hive_test_helper.dart';

void main() {
  group('WorkflowRepositoryImpl', () {
    late OrchestratorHiveBoxes boxes;
    late WorkflowRepository repository;

    const String projectId = '550e8400-e29b-41d4-a716-446655440000';
    const String otherProjectId = '660e8400-e29b-41d4-a716-446655440001';
    const String slug = 'payments-api';

    setUpAll(() async {
      await OrchestratorHiveTestHelper.setUpHive();
    });

    tearDownAll(() async {
      await OrchestratorHiveTestHelper.tearDownHive();
    });

    setUp(() async {
      boxes = await OrchestratorHiveTestHelper.openBoxes();
      repository = WorkflowRepositoryImpl(boxes: boxes);
    });

    tearDown(() async {
      await boxes.workflows.clear();
      await boxes.workflows.close();
      await boxes.prdRuns.close();
      await boxes.prdApprovals.close();
      await boxes.streamEvents.close();
    });

    test(
      'create returns slug collision failure for duplicate slug in same project',
      () async {
        final Either<Failure, WorkflowEntity> first = await repository.create(
          projectId: projectId,
          slug: slug,
          branchName: 'main',
        );
        expect(first.isRight(), isTrue);

        final Either<Failure, WorkflowEntity> second = await repository.create(
          projectId: projectId,
          slug: slug,
          branchName: 'develop',
        );

        expect(second.isLeft(), isTrue);
        expect(
          second.getLeft().toNullable(),
          isA<WorkflowPersistenceFailure>().having(
            (WorkflowPersistenceFailure failure) => failure.code,
            'code',
            WorkflowPersistenceFailureCode.slugCollision,
          ),
        );
      },
    );

    test(
      'listByProject returns only workflows for requested projectId',
      () async {
        await repository.create(
          projectId: projectId,
          slug: slug,
          branchName: 'main',
        );
        await repository.create(
          projectId: otherProjectId,
          slug: slug,
          branchName: 'main',
        );

        final Either<Failure, List<WorkflowEntity>> listResult =
            await repository.listByProject(projectId);

        final List<WorkflowEntity> workflows = listResult.getOrElse(
          (Failure _) => <WorkflowEntity>[],
        );
        expect(workflows, hasLength(1));
        expect(workflows.first.projectId, projectId);
      },
    );

    test('findBySlug returns null when slug is absent', () async {
      final WorkflowEntity? found = await repository.findBySlug(
        projectId: projectId,
        slug: 'missing-slug',
      );
      expect(found, isNull);
    });

    test(
      'rolls back filesystem directory when hive put fails after directory create',
      () async {
        final Directory tempRoot = await Directory.systemTemp.createTemp(
          'pulse_workflow_fs_rollback_',
        );
        addTearDown(() {
          if (tempRoot.existsSync()) {
            tempRoot.deleteSync(recursive: true);
          }
        });

        final Directory workflowsRoot = Directory(
          p.join(tempRoot.path, 'pulse', 'workflows'),
        );
        await workflowsRoot.create(recursive: true);
        final FilesystemArtifactServiceImpl artifactPersistenceService =
            FilesystemArtifactServiceImpl(workflowsRoot: workflowsRoot);

        final WorkflowRepository fsRepository = WorkflowRepositoryImpl(
          boxes: boxes,
          artifactPersistenceService: artifactPersistenceService,
          hivePutOverride: (String key, WorkflowEntity entity) async {
            throw StateError('simulated hive failure');
          },
        );

        final Either<Failure, WorkflowEntity> createResult = await fsRepository
            .create(
              projectId: projectId,
              slug: 'rollback-slug',
              branchName: 'main',
            );

        expect(createResult.isLeft(), isTrue);
        final Directory workflowDir = artifactPersistenceService
            .workflowDirectory(projectId: projectId, slug: 'rollback-slug');
        expect(workflowDir.existsSync(), isFalse);
        expect(
          boxes.workflows.containsKey('$projectId::rollback-slug'),
          isFalse,
        );
      },
    );
  });
}
