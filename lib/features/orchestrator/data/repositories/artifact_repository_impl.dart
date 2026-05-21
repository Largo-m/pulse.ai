import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/data/artifact_path_segment_validator.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/adr_entry.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_artifact_metadata.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/artifact_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/artifact_persistence_service.dart';

final class ArtifactRepositoryImpl implements ArtifactRepository {
  ArtifactRepositoryImpl({
    required ArtifactPersistenceService artifactPersistenceService,
    ArtifactPathSegmentValidator? pathSegmentValidator,
  }) : _artifactPersistenceService = artifactPersistenceService,
       _pathSegmentValidator =
           pathSegmentValidator ?? const ArtifactPathSegmentValidator();

  final ArtifactPersistenceService _artifactPersistenceService;
  final ArtifactPathSegmentValidator _pathSegmentValidator;

  @override
  Future<Either<Failure, String>> readPrdMarkdown({
    required String projectId,
    required String slug,
  }) async {
    final Either<Failure, void> projectValidation = _pathSegmentValidator
        .validateProjectId(projectId);
    if (projectValidation.isLeft()) {
      return left(projectValidation.getLeft().toNullable()!);
    }

    final Either<Failure, void> slugValidation = _pathSegmentValidator
        .validateSlug(slug);
    if (slugValidation.isLeft()) {
      return left(slugValidation.getLeft().toNullable()!);
    }

    return _artifactPersistenceService.readPrdMarkdown(
      projectId: projectId,
      slug: slug,
    );
  }

  @override
  Future<Either<Failure, void>> writePrdMarkdown({
    required String projectId,
    required String slug,
    required String markdown,
    required PrdArtifactMetadata metadata,
  }) async {
    final Either<Failure, void> projectValidation = _pathSegmentValidator
        .validateProjectId(projectId);
    if (projectValidation.isLeft()) {
      return left(projectValidation.getLeft().toNullable()!);
    }

    final Either<Failure, void> slugValidation = _pathSegmentValidator
        .validateSlug(slug);
    if (slugValidation.isLeft()) {
      return left(slugValidation.getLeft().toNullable()!);
    }

    return _artifactPersistenceService.writePrdMarkdown(
      projectId: projectId,
      slug: slug,
      markdown: markdown,
      metadata: metadata,
    );
  }

  @override
  Future<Either<Failure, List<AdrEntry>>> listAdrs({
    required String projectId,
    required String slug,
  }) async {
    final Either<Failure, void> projectValidation = _pathSegmentValidator
        .validateProjectId(projectId);
    if (projectValidation.isLeft()) {
      return left(projectValidation.getLeft().toNullable()!);
    }

    final Either<Failure, void> slugValidation = _pathSegmentValidator
        .validateSlug(slug);
    if (slugValidation.isLeft()) {
      return left(slugValidation.getLeft().toNullable()!);
    }

    return _artifactPersistenceService.listAdrs(
      projectId: projectId,
      slug: slug,
    );
  }
}
