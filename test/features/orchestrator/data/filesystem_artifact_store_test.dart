import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:path/path.dart' as p;
import 'package:pulse_ai/core/error/artifact_persistence_failure.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/data/filesystem_artifact_store.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/adr_entry.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_artifact_metadata.dart';

void main() {
  group('FilesystemArtifactStore', () {
    late Directory tempRoot;
    late Directory workflowsRoot;
    late FilesystemArtifactStore store;

    const String projectId = '550e8400-e29b-41d4-a716-446655440000';
    const String slug = 'auth-flow';

    setUp(() async {
      tempRoot = await Directory.systemTemp.createTemp('pulse_artifact_test_');
      workflowsRoot = Directory(p.join(tempRoot.path, 'pulse', 'workflows'));
      await workflowsRoot.create(recursive: true);
      store = FilesystemArtifactStore(workflowsRoot: workflowsRoot);
    });

    tearDown(() async {
      if (await tempRoot.exists()) {
        await tempRoot.delete(recursive: true);
      }
    });

    test(
      'writePrdMarkdown then readPrdMarkdown returns identical content',
      () async {
        const String markdown = '# PRD\n\nConteúdo de teste.';

        final Either<Failure, void> writeResult = await store.writePrdMarkdown(
          projectId: projectId,
          slug: slug,
          markdown: markdown,
          metadata: PrdArtifactMetadata(
            lastEditedAt: DateTime.utc(2026, 5, 20, 10),
            sourceRunId: 'run-1',
          ),
        );
        expect(writeResult.isRight(), isTrue);

        final Either<Failure, String> readResult = await store.readPrdMarkdown(
          projectId: projectId,
          slug: slug,
        );
        expect(readResult.getOrElse((Failure _) => ''), markdown);
      },
    );

    test(
      'readPrdMarkdown returns empty string when prd.md is missing',
      () async {
        final Either<Failure, String> readResult = await store.readPrdMarkdown(
          projectId: projectId,
          slug: 'missing-workflow',
        );

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
            FilesystemArtifactStore.adrsDirectoryName,
          ),
        );
        await adrsDir.create(recursive: true);
        await File(p.join(adrsDir.path, 'adr-002.md')).writeAsString('# ADR 2');
        await File(p.join(adrsDir.path, 'adr-001.md')).writeAsString('# ADR 1');

        final Either<Failure, List<AdrEntry>> listResult = await store.listAdrs(
          projectId: projectId,
          slug: slug,
        );

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

        await store.writePrdMarkdown(
          projectId: projectId,
          slug: slug,
          markdown: original,
          metadata: PrdArtifactMetadata(
            lastEditedAt: DateTime.utc(2026, 5, 20, 9),
          ),
        );

        var renameAttempts = 0;
        final FilesystemArtifactStore failingStore = FilesystemArtifactStore(
          workflowsRoot: workflowsRoot,
          atomicRename: (File source, File target) async {
            renameAttempts++;
            if (renameAttempts == 1 &&
                p.basename(target.path) ==
                    FilesystemArtifactStore.prdFileName) {
              throw const FileSystemException('simulated rename failure');
            }
            if (await target.exists()) {
              await target.delete();
            }
            await source.rename(target.path);
          },
        );

        final Either<Failure, void> writeResult = await failingStore
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

        final Either<Failure, String> readResult = await store.readPrdMarkdown(
          projectId: projectId,
          slug: slug,
        );
        expect(readResult.getOrElse((Failure _) => ''), original);
      },
    );

    test(
      'readPrdMarkdown returns ioError when prd file is not readable',
      () async {
        if (!Platform.isMacOS && !Platform.isLinux) {
          return;
        }

        await store.writePrdMarkdown(
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
            FilesystemArtifactStore.prdFileName,
          ),
        );
        await Process.run('chmod', <String>['000', prdFile.path]);
        addTearDown(() async {
          await Process.run('chmod', <String>['644', prdFile.path]);
        });

        final Either<Failure, String> readResult = await store.readPrdMarkdown(
          projectId: projectId,
          slug: slug,
        );

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
          FilesystemArtifactStore.adrsDirectoryName,
        ),
      );
      await adrsDir.create(recursive: true);
      await File(p.join(adrsDir.path, 'notes.txt')).writeAsString('skip');
      await Directory(p.join(adrsDir.path, 'ignored-dir')).create();
      await File(p.join(adrsDir.path, 'adr-001.md')).writeAsString('# ADR');

      final Either<Failure, List<AdrEntry>> listResult = await store.listAdrs(
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
        await store.writePrdMarkdown(
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
            FilesystemArtifactStore.metadataFileName,
          ),
        );
        expect(await metadataFile.exists(), isTrue);
        expect(await metadataFile.readAsString(), contains('run-meta'));
      },
    );

    test(
      'createFromApplicationSupport resolves pulse/workflows under app support',
      () async {
        final FilesystemArtifactStore resolvedStore =
            await FilesystemArtifactStore.createFromApplicationSupport(
              resolveApplicationSupportDirectory: () async => tempRoot,
            );

        await resolvedStore.writePrdMarkdown(
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
        expect(await prdFile.exists(), isTrue);
      },
    );

    test('creates pulse/workflows layout under workflows root', () async {
      await store.writePrdMarkdown(
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
      expect(await prdFile.exists(), isTrue);
      expect(
        store.workflowDirectory(projectId: projectId, slug: slug).path,
        p.join(workflowsRoot.path, projectId, slug),
      );
    });
  });
}
