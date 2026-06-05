import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/workflow_persistence_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/workflow_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/validators/workflow_slug_validator.dart';

final class CreateWorkflowUseCase {
  CreateWorkflowUseCase({
    required WorkflowRepository workflowRepository,
    WorkflowSlugValidator? slugValidator,
  }) : _workflowRepository = workflowRepository,
       _slugValidator = slugValidator ?? const WorkflowSlugValidator();

  final WorkflowRepository _workflowRepository;
  final WorkflowSlugValidator _slugValidator;

  Future<Either<Failure, WorkflowEntity>> call({
    required String projectId,
    required String slug,
    required String branchName,
    String? directive,
  }) async {
    final Either<Failure, void> slugValidation = _slugValidator.validate(slug);
    if (slugValidation.isLeft()) {
      return left(slugValidation.getLeft().toNullable()!);
    }

    final WorkflowEntity? existing = await _workflowRepository.findBySlug(
      projectId: projectId,
      slug: slug,
    );
    if (existing != null) {
      return left(const WorkflowPersistenceFailure.slugCollision());
    }

    return _workflowRepository.create(
      projectId: projectId,
      slug: slug,
      branchName: branchName,
      directive: directive,
    );
  }
}
