import 'dart:convert';
import 'dart:io';

import 'package:fpdart/fpdart.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:pulse_ai/core/error/artifact_persistence_failure.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/adr_entry.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_artifact_metadata.dart';

typedef ArtifactAtomicRename = Future<void> Function(File source, File target);

final class FilesystemArtifactStore {
  FilesystemArtifactStore({
    required Directory workflowsRoot,
    ArtifactAtomicRename? atomicRename,
  }) : _workflowsRoot = workflowsRoot,
       _atomicRename = atomicRename ?? _defaultAtomicRename;

  final Directory _workflowsRoot;
  final ArtifactAtomicRename _atomicRename;

  static const String prdFileName = 'prd.md';
  static const String metadataFileName = 'prd.meta.json';
  static const String adrsDirectoryName = 'adrs';
  static final RegExp _adrFileNamePattern = RegExp(r'^adr-(\d{3})\.md$');

  static Future<FilesystemArtifactStore> createFromApplicationSupport({
    Future<Directory> Function()? resolveApplicationSupportDirectory,
  }) async {
    final Directory appSupport = resolveApplicationSupportDirectory != null
        ? await resolveApplicationSupportDirectory()
        : await getApplicationSupportDirectory();
    final Directory workflowsRoot = Directory(
      p.join(appSupport.path, 'pulse', 'workflows'),
    );
    return FilesystemArtifactStore(workflowsRoot: workflowsRoot);
  }

  Directory workflowDirectory({
    required String projectId,
    required String slug,
  }) {
    return Directory(p.join(_workflowsRoot.path, projectId, slug));
  }

  Future<Either<Failure, String>> readPrdMarkdown({
    required String projectId,
    required String slug,
  }) async {
    try {
      final File prdFile = _prdFile(projectId: projectId, slug: slug);
      if (!await prdFile.exists()) {
        return right('');
      }
      return right(await prdFile.readAsString());
    } on IOException {
      return left(const ArtifactPersistenceFailure.ioError());
    }
  }

  Future<Either<Failure, void>> writePrdMarkdown({
    required String projectId,
    required String slug,
    required String markdown,
    required PrdArtifactMetadata metadata,
  }) async {
    try {
      final Directory workflowDir = workflowDirectory(
        projectId: projectId,
        slug: slug,
      );
      await workflowDir.create(recursive: true);

      final File prdFile = File(p.join(workflowDir.path, prdFileName));
      final File tempFile = File('${prdFile.path}.tmp');

      await tempFile.writeAsString(markdown, flush: true);
      await _atomicRename(tempFile, prdFile);

      final File metadataFile = File(
        p.join(workflowDir.path, metadataFileName),
      );
      final File metadataTemp = File('${metadataFile.path}.tmp');
      final String metadataJson = jsonEncode(<String, Object?>{
        'lastEditedAt': metadata.lastEditedAt.toUtc().toIso8601String(),
        'sourceRunId': metadata.sourceRunId,
      });
      await metadataTemp.writeAsString(metadataJson, flush: true);
      await _atomicRename(metadataTemp, metadataFile);

      return right(null);
    } on IOException {
      return left(const ArtifactPersistenceFailure.ioError());
    }
  }

  Future<Either<Failure, List<AdrEntry>>> listAdrs({
    required String projectId,
    required String slug,
  }) async {
    try {
      final Directory adrsDir = _adrsDirectory(
        projectId: projectId,
        slug: slug,
      );
      if (!await adrsDir.exists()) {
        return right(<AdrEntry>[]);
      }

      final List<FileSystemEntity> entities = await adrsDir.list().toList();
      final List<AdrEntry> entries = <AdrEntry>[];

      for (final FileSystemEntity entity in entities) {
        if (entity is! File) {
          continue;
        }

        final String fileName = p.basename(entity.path);
        final RegExpMatch? match = _adrFileNamePattern.firstMatch(fileName);
        if (match == null) {
          continue;
        }

        final int sequenceNumber = int.parse(match.group(1)!);
        final String markdown = await entity.readAsString();
        entries.add(
          AdrEntry(
            fileName: fileName,
            sequenceNumber: sequenceNumber,
            markdown: markdown,
          ),
        );
      }

      entries.sort(
        (AdrEntry a, AdrEntry b) =>
            a.sequenceNumber.compareTo(b.sequenceNumber),
      );

      return right(entries);
    } on IOException {
      return left(const ArtifactPersistenceFailure.ioError());
    }
  }

  File _prdFile({required String projectId, required String slug}) {
    return File(
      p.join(
        workflowDirectory(projectId: projectId, slug: slug).path,
        prdFileName,
      ),
    );
  }

  Directory _adrsDirectory({required String projectId, required String slug}) {
    return Directory(
      p.join(
        workflowDirectory(projectId: projectId, slug: slug).path,
        adrsDirectoryName,
      ),
    );
  }

  static Future<void> _defaultAtomicRename(File source, File target) async {
    if (await target.exists()) {
      await target.delete();
    }
    await source.rename(target.path);
  }
}
