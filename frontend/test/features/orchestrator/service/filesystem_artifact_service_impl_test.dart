import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:path/path.dart' as p;
import 'package:pulse_ai/core/error/artifact_persistence_failure.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/adr_entry.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_artifact_metadata.dart';
import 'package:pulse_ai/features/orchestrator/service/filesystem_artifact_service_impl.dart';

void main() {
  group('FilesystemArtifactServiceImpl', () {
    late Directory tempRoot;
    late Directory workflowsRoot;
    late FilesystemArtifactServiceImpl service;

    const String projectId = '550e8400-e29b-41d4-a716-446655440000';
    const String slug = 'auth-flow';

    setUp(() async {
      tempRoot = await Directory.systemTemp.createTemp('pulse_artifact_test_');
      workflowsRoot = Directory(p.join(tempRoot.path, 'pulse', 'workflows'));
      await workflowsRoot.create(recursive: true);
      service = FilesystemArtifactServiceImpl(workflowsRoot: workflowsRoot);
    });

    tearDown(() async {
      if (tempRoot.existsSync()) {
        tempRoot.deleteSync(recursive: true);
      }
    });

    test(
      'writePrdMarkdown then readPrdMarkdown returns identical content',
      () async {
        const String markdown = '# PRD\n\nConteúdo de teste.';

        final Either<Failure, void> writeResult = await service
            .writePrdMarkdown(
              projectId: projectId,
              slug: slug,
              markdown: markdown,
              metadata: PrdArtifactMetadata(
                lastEditedAt: DateTime.utc(2026, 5, 20, 10),
                sourceRunId: 'run-1',
              ),
            );
        expect(writeResult.isRight(), isTrue);

        final Either<Failure, String> readResult = await service
            .readPrdMarkdown(projectId: projectId, slug: slug);
        expect(readResult.getOrElse((Failure _) => ''), markdown);
      },
    );

    test(
      'readPrdMarkdown returns empty string when prd.md is missing',
      () async {
        final Either<Failure, String> readResult = await service
            .readPrdMarkdown(projectId: projectId, slug: 'missing-workflow');

        expect(readResult.getOrElse((Failure _) => 'missing'), '');
      },
    );

    test(
      'listAdrs returns entries ordered by sequence when adrs exist',
      () async {
        final Directory adrsDir = Directory(
          p.join(
            workflowsRoot.path,
            projectId,
            slug,
            FilesystemArtifactServiceImpl.adrsDirectoryName,
          ),
        );
        await adrsDir.create(recursive: true);
        await File(p.join(adrsDir.path, 'adr-002.md')).writeAsString('# ADR 2');
        await File(p.join(adrsDir.path, 'adr-001.md')).writeAsString('# ADR 1');

        final Either<Failure, List<AdrEntry>> listResult = await service
            .listAdrs(projectId: projectId, slug: slug);

        final List<AdrEntry> entries = listResult.getOrElse(
          (Failure _) => <AdrEntry>[],
        );
        expect(entries, hasLength(2));
        expect(entries.first.fileName, 'adr-001.md');
        expect(entries.first.sequenceNumber, 1);
        expect(entries.last.fileName, 'adr-002.md');
        expect(entries.last.sequenceNumber, 2);
      },
    );

    test(
      'write failure on atomic rename leaves prior prd.md unchanged',
      () async {
        const String original = '# Original PRD';
        const String updated = '# Updated PRD';

        await service.writePrdMarkdown(
          projectId: projectId,
          slug: slug,
          markdown: original,
          metadata: PrdArtifactMetadata(
            lastEditedAt: DateTime.utc(2026, 5, 20, 9),
          ),
        );

        var renameAttempts = 0;
        final FilesystemArtifactServiceImpl failingService =
            FilesystemArtifactServiceImpl(
              workflowsRoot: workflowsRoot,
              atomicRename: (File source, File target) async {
                renameAttempts++;
                if (renameAttempts == 1 &&
                    p.basename(target.path) ==
                        FilesystemArtifactServiceImpl.prdFileName) {
                  throw const FileSystemException('simulated rename failure');
                }
                if (target.existsSync()) {
                  target.deleteSync();
                }
                await source.rename(target.path);
              },
            );

        final Either<Failure, void> writeResult = await failingService
            .writePrdMarkdown(
              projectId: projectId,
              slug: slug,
              markdown: updated,
              metadata: PrdArtifactMetadata(
                lastEditedAt: DateTime.utc(2026, 5, 20, 11),
              ),
            );

        expect(writeResult.isLeft(), isTrue);
        expect(
          writeResult.getLeft().toNullable(),
          isA<ArtifactPersistenceFailure>().having(
            (ArtifactPersistenceFailure f) => f.code,
            'code',
            ArtifactPersistenceFailureCode.ioError,
          ),
        );

        final Either<Failure, String> readResult = await service
            .readPrdMarkdown(projectId: projectId, slug: slug);
        expect(readResult.getOrElse((Failure _) => ''), original);
      },
    );

    test(
      'readPrdMarkdown returns ioError when prd file is not readable',
      () async {
        if (!Platform.isMacOS && !Platform.isLinux) {
          return;
        }

        await service.writePrdMarkdown(
          projectId: projectId,
          slug: slug,
          markdown: '# PRD',
          metadata: PrdArtifactMetadata(
            lastEditedAt: DateTime.utc(2026, 5, 20, 19),
          ),
        );

        final File prdFile = File(
          p.join(
            workflowsRoot.path,
            projectId,
            slug,
            FilesystemArtifactServiceImpl.prdFileName,
          ),
        );
        await Process.run('chmod', <String>['000', prdFile.path]);
        addTearDown(() async {
          await Process.run('chmod', <String>['644', prdFile.path]);
        });

        final Either<Failure, String> readResult = await service
            .readPrdMarkdown(projectId: projectId, slug: slug);

        expect(readResult.isLeft(), isTrue);
        expect(
          readResult.getLeft().toNullable(),
          isA<ArtifactPersistenceFailure>().having(
            (ArtifactPersistenceFailure f) => f.code,
            'code',
            ArtifactPersistenceFailureCode.ioError,
          ),
        );
      },
    );

    test('listAdrs ignores non-matching files in adrs directory', () async {
      final Directory adrsDir = Directory(
        p.join(
          workflowsRoot.path,
          projectId,
          slug,
          FilesystemArtifactServiceImpl.adrsDirectoryName,
        ),
      );
      await adrsDir.create(recursive: true);
      await File(p.join(adrsDir.path, 'notes.txt')).writeAsString('skip');
      await Directory(p.join(adrsDir.path, 'ignored-dir')).create();
      await File(p.join(adrsDir.path, 'adr-001.md')).writeAsString('# ADR');

      final Either<Failure, List<AdrEntry>> listResult = await service.listAdrs(
        projectId: projectId,
        slug: slug,
      );

      final List<AdrEntry> entries = listResult.getOrElse(
        (Failure _) => <AdrEntry>[],
      );
      expect(entries, hasLength(1));
      expect(entries.single.fileName, 'adr-001.md');
    });

    test(
      'writePrdMarkdown persists metadata json alongside prd markdown',
      () async {
        await service.writePrdMarkdown(
          projectId: projectId,
          slug: slug,
          markdown: '# PRD',
          metadata: PrdArtifactMetadata(
            lastEditedAt: DateTime.utc(2026, 5, 20, 13),
            sourceRunId: 'run-meta',
          ),
        );

        final File metadataFile = File(
          p.join(
            workflowsRoot.path,
            projectId,
            slug,
            FilesystemArtifactServiceImpl.metadataFileName,
          ),
        );
        expect(metadataFile.existsSync(), isTrue);
        expect(metadataFile.readAsStringSync(), contains('run-meta'));
      },
    );

    test(
      'createFromApplicationSupport resolves pulse/workflows under app support',
      () async {
        final FilesystemArtifactServiceImpl resolvedService =
            await FilesystemArtifactServiceImpl.createFromApplicationSupport(
              resolveApplicationSupportDirectory: () async => tempRoot,
            );

        await resolvedService.writePrdMarkdown(
          projectId: projectId,
          slug: 'from-app-support',
          markdown: '# From support root',
          metadata: PrdArtifactMetadata(
            lastEditedAt: DateTime.utc(2026, 5, 20, 18),
          ),
        );

        final File prdFile = File(
          p.join(
            tempRoot.path,
            'pulse',
            'workflows',
            projectId,
            'from-app-support',
            'prd.md',
          ),
        );
        expect(prdFile.existsSync(), isTrue);
      },
    );

    test('creates pulse/workflows layout under workflows root', () async {
      await service.writePrdMarkdown(
        projectId: projectId,
        slug: slug,
        markdown: '# PRD',
        metadata: PrdArtifactMetadata(
          lastEditedAt: DateTime.utc(2026, 5, 20, 12),
        ),
      );

      final File prdFile = File(
        p.join(workflowsRoot.path, projectId, slug, 'prd.md'),
      );
      expect(prdFile.existsSync(), isTrue);
      expect(
        service.workflowDirectory(projectId: projectId, slug: slug).path,
        p.join(workflowsRoot.path, projectId, slug),
      );
    });

    test(
      'ensureWorkflowDirectory creates directory and deleteWorkflowDirectory removes it',
      () async {
        final Directory workflowDir = service.workflowDirectory(
          projectId: projectId,
          slug: 'dir-lifecycle',
        );
        expect(workflowDir.existsSync(), isFalse);

        final Either<Failure, void> ensureResult = await service
            .ensureWorkflowDirectory(
              projectId: projectId,
              slug: 'dir-lifecycle',
            );
        expect(ensureResult.isRight(), isTrue);
        expect(workflowDir.existsSync(), isTrue);

        final Either<Failure, void> deleteResult = await service
            .deleteWorkflowDirectory(
              projectId: projectId,
              slug: 'dir-lifecycle',
            );
        expect(deleteResult.isRight(), isTrue);
        expect(workflowDir.existsSync(), isFalse);
      },
    );
  });
}
