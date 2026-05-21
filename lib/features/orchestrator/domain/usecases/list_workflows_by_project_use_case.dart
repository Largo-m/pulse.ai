import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/workflow_repository.dart';

final class ListWorkflowsByProjectUseCase {
  ListWorkflowsByProjectUseCase(this._workflowRepository);

  final WorkflowRepository _workflowRepository;

  Future<Either<Failure, List<WorkflowEntity>>> call(String projectId) {
    return _workflowRepository.listByProject(projectId);
  }
}
