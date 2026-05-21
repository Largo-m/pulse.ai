import 'dart:convert';
import 'dart:io';

import 'package:fpdart/fpdart.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:pulse_ai/core/error/artifact_persistence_failure.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/adr_entry.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_artifact_metadata.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/stream_event_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/artifact_persistence_service.dart';

typedef ArtifactAtomicRename = Future<void> Function(File source, File target);

final class FilesystemArtifactServiceImpl
    implements ArtifactPersistenceService {
  FilesystemArtifactServiceImpl({
    required Directory workflowsRoot,
    ArtifactAtomicRename? atomicRename,
  }) : _workflowsRoot = workflowsRoot,
       _atomicRename = atomicRename ?? _defaultAtomicRename;

  final Directory _workflowsRoot;
  final ArtifactAtomicRename _atomicRename;

  static const String prdFileName = 'prd.md';
  static const String metadataFileName = 'prd.meta.json';
  static const String adrsDirectoryName = 'adrs';
  static const String streamsDirectoryName = 'streams';
  static final RegExp _adrFileNamePattern = RegExp(r'^adr-(\d{3})\.md$');

  static Future<FilesystemArtifactServiceImpl> createFromApplicationSupport({
    Future<Directory> Function()? resolveApplicationSupportDirectory,
  }) async {
    final Directory appSupport = resolveApplicationSupportDirectory != null
        ? await resolveApplicationSupportDirectory()
        : await getApplicationSupportDirectory();
    final Directory workflowsRoot = Directory(
      p.join(appSupport.path, 'pulse', 'workflows'),
    );
    return FilesystemArtifactServiceImpl(workflowsRoot: workflowsRoot);
  }

  Directory workflowDirectory({
    required String projectId,
    required String slug,
  }) {
    return Directory(p.join(_workflowsRoot.path, projectId, slug));
  }

  @override
  Future<Either<Failure, void>> ensureWorkflowDirectory({
    required String projectId,
    required String slug,
  }) async {
    try {
      final Directory directory = workflowDirectory(
        projectId: projectId,
        slug: slug,
      );
      await directory.create(recursive: true);
      return right(null);
    } on IOException {
      return left(const ArtifactPersistenceFailure.ioError());
    }
  }

  @override
  Future<Either<Failure, void>> deleteWorkflowDirectory({
    required String projectId,
    required String slug,
  }) async {
    try {
      final Directory directory = workflowDirectory(
        projectId: projectId,
        slug: slug,
      );
      if (directory.existsSync()) {
        directory.deleteSync(recursive: true);
      }
      return right(null);
    } on IOException {
      return left(const ArtifactPersistenceFailure.ioError());
    }
  }

  @override
  Future<Either<Failure, String>> readPrdMarkdown({
    required String projectId,
    required String slug,
  }) async {
    try {
      final File prdFile = _prdFile(projectId: projectId, slug: slug);
      if (!prdFile.existsSync()) {
        return right('');
      }
      return right(prdFile.readAsStringSync());
    } on IOException {
      return left(const ArtifactPersistenceFailure.ioError());
    }
  }

  @override
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

  @override
  Future<Either<Failure, List<AdrEntry>>> listAdrs({
    required String projectId,
    required String slug,
  }) async {
    try {
      final Directory adrsDir = _adrsDirectory(
        projectId: projectId,
        slug: slug,
      );
      if (!adrsDir.existsSync()) {
        return right(<AdrEntry>[]);
      }

      final List<FileSystemEntity> entities = adrsDir.listSync();
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
        final String markdown = entity.readAsStringSync();
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

  @override
  Future<Either<Failure, void>> writeAdrMarkdown({
    required String projectId,
    required String slug,
    required AdrEntry entry,
  }) async {
    try {
      final Directory adrsDir = _adrsDirectory(
        projectId: projectId,
        slug: slug,
      );
      await adrsDir.create(recursive: true);

      final File adrFile = File(p.join(adrsDir.path, entry.fileName));
      final File tempFile = File('${adrFile.path}.tmp');
      await tempFile.writeAsString(entry.markdown, flush: true);
      await _atomicRename(tempFile, adrFile);
      return right(null);
    } on IOException {
      return left(const ArtifactPersistenceFailure.ioError());
    }
  }

  @override
  Future<Either<Failure, void>> appendStreamJsonl({
    required String projectId,
    required String slug,
    required String runId,
    required StreamEventEntity event,
  }) async {
    try {
      final Directory streamsDir = Directory(
        p.join(
          workflowDirectory(projectId: projectId, slug: slug).path,
          streamsDirectoryName,
        ),
      );
      await streamsDir.create(recursive: true);

      final File jsonlFile = File(p.join(streamsDir.path, '$runId.jsonl'));
      final String line = jsonEncode(<String, Object>{
        'sequence': event.sequence,
        'eventType': event.eventType,
        'payloadSummary': event.payloadSummary,
        'timestamp': event.timestamp.toUtc().toIso8601String(),
      });
      await jsonlFile.writeAsString(
        '$line\n',
        mode: FileMode.append,
        flush: true,
      );
      return right(null);
    } on IOException {
      return left(const ArtifactPersistenceFailure.ioError());
    }
  }

  static Future<void> _defaultAtomicRename(File source, File target) async {
    if (target.existsSync()) {
      target.deleteSync();
    }
    await source.rename(target.path);
  }
}
