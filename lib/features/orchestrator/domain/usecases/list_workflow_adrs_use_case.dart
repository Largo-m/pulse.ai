import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/adr_entry.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/artifact_repository.dart';

final class ListWorkflowAdrsUseCase {
  ListWorkflowAdrsUseCase(this._artifactRepository);

  final ArtifactRepository _artifactRepository;

  Future<Either<Failure, List<AdrEntry>>> call({
    required String projectId,
    required String slug,
  }) {
    return _artifactRepository.listAdrs(projectId: projectId, slug: slug);
  }
}
