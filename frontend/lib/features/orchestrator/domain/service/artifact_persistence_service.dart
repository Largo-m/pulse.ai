import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/adr_entry.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_artifact_metadata.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/stream_event_entity.dart';

abstract interface class ArtifactPersistenceService {
  Future<Either<Failure, String>> readPrdMarkdown({
    required String projectId,
    required String slug,
  });

  Future<Either<Failure, void>> writePrdMarkdown({
    required String projectId,
    required String slug,
    required String markdown,
    required PrdArtifactMetadata metadata,
  });

  Future<Either<Failure, List<AdrEntry>>> listAdrs({
    required String projectId,
    required String slug,
  });

  Future<Either<Failure, void>> ensureWorkflowDirectory({
    required String projectId,
    required String slug,
  });

  Future<Either<Failure, void>> deleteWorkflowDirectory({
    required String projectId,
    required String slug,
  });

  Future<Either<Failure, void>> writeAdrMarkdown({
    required String projectId,
    required String slug,
    required AdrEntry entry,
  });

  Future<Either<Failure, void>> appendStreamJsonl({
    required String projectId,
    required String slug,
    required String runId,
    required StreamEventEntity event,
  });
}
