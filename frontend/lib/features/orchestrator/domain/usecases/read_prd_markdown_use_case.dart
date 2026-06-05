import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/artifact_repository.dart';

final class ReadPrdMarkdownUseCase {
  ReadPrdMarkdownUseCase(this._artifactRepository);

  final ArtifactRepository _artifactRepository;

  Future<Either<Failure, String>> call({
    required String projectId,
    required String slug,
  }) {
    return _artifactRepository.readPrdMarkdown(
      projectId: projectId,
      slug: slug,
    );
  }
}
