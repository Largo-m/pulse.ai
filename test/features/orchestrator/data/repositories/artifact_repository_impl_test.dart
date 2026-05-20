import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:path/path.dart' as p;
import 'package:pulse_ai/core/error/artifact_persistence_failure.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/data/filesystem_artifact_store.dart';
import 'package:pulse_ai/features/orchestrator/data/repositories/artifact_repository_impl.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/adr_entry.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_artifact_metadata.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/artifact_repository.dart';

void main() {
  group('ArtifactRepositoryImpl', () {
    late Directory tempRoot;
    late Directory workflowsRoot;
    late ArtifactRepository repository;

    const String projectId = '550e8400-e29b-41d4-a716-446655440000';
    const String slug = 'payments-api';

    setUp(() async {
      tempRoot = await Directory.systemTemp.createTemp(
        'pulse_artifact_repo_test_',
      );
      workflowsRoot = Directory(p.join(tempRoot.path, 'pulse', 'workflows'));
      await workflowsRoot.create(recursive: true);
      final FilesystemArtifactStore store = FilesystemArtifactStore(
        workflowsRoot: workflowsRoot,
      );
      repository = ArtifactRepositoryImpl(store: store);
    });

    tearDown(() async {
      if (await tempRoot.exists()) {
        await tempRoot.delete(recursive: true);
      }
    });

    test(
      'writePrdMarkdown then readPrdMarkdown returns identical content',
      () async {
        const String markdown = '# PRD\n\nFluxo de pagamentos.';

        final Either<Failure, void> writeResult = await repository
            .writePrdMarkdown(
              projectId: projectId,
              slug: slug,
              markdown: markdown,
              metadata: PrdArtifactMetadata(
                lastEditedAt: DateTime.utc(2026, 5, 20, 14),
              ),
            );
        expect(writeResult.isRight(), isTrue);

        final Either<Failure, String> readResult = await repository
            .readPrdMarkdown(projectId: projectId, slug: slug);
        expect(readResult.getOrElse((Failure _) => ''), markdown);
      },
    );

    test('listAdrs returns adr entries sorted by sequence number', () async {
      final Directory adrsDir = Directory(
        p.join(
          workflowsRoot.path,
          projectId,
          slug,
          FilesystemArtifactStore.adrsDirectoryName,
        ),
      );
      await adrsDir.create(recursive: true);
      await File(p.join(adrsDir.path, 'adr-002.md')).writeAsString('two');
      await File(p.join(adrsDir.path, 'adr-001.md')).writeAsString('one');

      final Either<Failure, List<AdrEntry>> listResult = await repository
          .listAdrs(projectId: projectId, slug: slug);

      final List<AdrEntry> entries = listResult.getOrElse(
        (Failure _) => <AdrEntry>[],
      );
      expect(entries.map((AdrEntry e) => e.fileName).toList(), <String>[
        'adr-001.md',
        'adr-002.md',
      ]);
    });

    test(
      'rejects invalid slug path segments before touching filesystem',
      () async {
        final Either<Failure, void> writeResult = await repository
            .writePrdMarkdown(
              projectId: projectId,
              slug: '../escape',
              markdown: '# Bad',
              metadata: PrdArtifactMetadata(
                lastEditedAt: DateTime.utc(2026, 5, 20, 15),
              ),
            );

        expect(writeResult.isLeft(), isTrue);
        expect(
          writeResult.getLeft().toNullable(),
          isA<ArtifactPersistenceFailure>().having(
            (ArtifactPersistenceFailure f) => f.code,
            'code',
            ArtifactPersistenceFailureCode.invalidPathSegment,
          ),
        );

        final Directory escapedDir = Directory(
          p.join(workflowsRoot.path, projectId, '..'),
        );
        expect(await escapedDir.exists(), isFalse);
      },
    );

    test('rejects empty projectId on read', () async {
      final Either<Failure, String> readResult = await repository
          .readPrdMarkdown(projectId: '', slug: slug);

      expect(readResult.isLeft(), isTrue);
    });

    test(
      'rejects empty slug on write without creating workflow directory',
      () async {
        final Either<Failure, void> writeResult = await repository
            .writePrdMarkdown(
              projectId: projectId,
              slug: '',
              markdown: '# PRD',
              metadata: PrdArtifactMetadata(
                lastEditedAt: DateTime.utc(2026, 5, 20, 17),
              ),
            );

        expect(writeResult.isLeft(), isTrue);
        expect(
          await Directory(p.join(workflowsRoot.path, projectId, '')).exists(),
          isFalse,
        );
      },
    );

    test('rejects invalid projectId on listAdrs', () async {
      final Either<Failure, List<AdrEntry>> listResult = await repository
          .listAdrs(projectId: '..', slug: slug);

      expect(listResult.isLeft(), isTrue);
    });

    test('rejects invalid projectId on writePrdMarkdown', () async {
      final Either<Failure, void> writeResult = await repository
          .writePrdMarkdown(
            projectId: '/bad',
            slug: slug,
            markdown: '# PRD',
            metadata: PrdArtifactMetadata(
              lastEditedAt: DateTime.utc(2026, 5, 20, 18),
            ),
          );

      expect(writeResult.isLeft(), isTrue);
    });

    test(
      'integration layout resolves artifacts by projectId and slug only',
      () async {
        await repository.writePrdMarkdown(
          projectId: projectId,
          slug: slug,
          markdown: '# Scoped PRD',
          metadata: PrdArtifactMetadata(
            lastEditedAt: DateTime.utc(2026, 5, 20, 16),
          ),
        );

        final File prdFile = File(
          p.join(workflowsRoot.path, projectId, slug, 'prd.md'),
        );
        expect(await prdFile.exists(), isTrue);
        expect(await prdFile.readAsString(), '# Scoped PRD');
      },
    );
  });
}
