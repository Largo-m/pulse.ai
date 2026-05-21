import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/artifact_persistence_failure.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/adr_entry.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_artifact_metadata.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/stream_event_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_key.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/artifact_repository.dart';

final class FakeArtifactRepository implements ArtifactRepository {
  final Map<String, String> prdMarkdownByKey = <String, String>{};
  final Map<String, PrdArtifactMetadata> metadataByKey =
      <String, PrdArtifactMetadata>{};
  final Map<String, List<AdrEntry>> adrsByKey = <String, List<AdrEntry>>{};
  final List<StreamEventEntity> streamJsonlEvents = <StreamEventEntity>[];

  @override
  Future<Either<Failure, String>> readPrdMarkdown({
    required String projectId,
    required String slug,
  }) async {
    final String key = WorkflowKey.compose(projectId: projectId, slug: slug);
    final String? markdown = prdMarkdownByKey[key];
    if (markdown == null) {
      return left(const ArtifactPersistenceFailure.notFound());
    }
    return right(markdown);
  }

  @override
  Future<Either<Failure, void>> writePrdMarkdown({
    required String projectId,
    required String slug,
    required String markdown,
    required PrdArtifactMetadata metadata,
  }) async {
    final String key = WorkflowKey.compose(projectId: projectId, slug: slug);
    prdMarkdownByKey[key] = markdown;
    metadataByKey[key] = metadata;
    return right(null);
  }

  @override
  Future<Either<Failure, List<AdrEntry>>> listAdrs({
    required String projectId,
    required String slug,
  }) async {
    final String key = WorkflowKey.compose(projectId: projectId, slug: slug);
    return right(
      List<AdrEntry>.unmodifiable(adrsByKey[key] ?? const <AdrEntry>[]),
    );
  }

  @override
  Future<Either<Failure, void>> writeAdrMarkdown({
    required String projectId,
    required String slug,
    required AdrEntry entry,
  }) async {
    final String key = WorkflowKey.compose(projectId: projectId, slug: slug);
    final List<AdrEntry> entries = List<AdrEntry>.from(
      adrsByKey[key] ?? const <AdrEntry>[],
    );
    entries.removeWhere((AdrEntry item) => item.fileName == entry.fileName);
    entries.add(entry);
    adrsByKey[key] = entries;
    return right(null);
  }

  @override
  Future<Either<Failure, void>> appendStreamJsonl({
    required String projectId,
    required String slug,
    required String runId,
    required StreamEventEntity event,
  }) async {
    streamJsonlEvents.add(event);
    return right(null);
  }
}
