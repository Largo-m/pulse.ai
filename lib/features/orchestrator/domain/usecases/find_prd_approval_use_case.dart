import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_key.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/prd_run_repository.dart';

final class FindPrdApprovalUseCase {
  FindPrdApprovalUseCase(this._prdRunRepository);

  final PrdRunRepository _prdRunRepository;

  Future<PrdApprovalEntity?> call({
    required String projectId,
    required String slug,
  }) {
    final String workflowKey = WorkflowKey.compose(
      projectId: projectId,
      slug: slug,
    );
    return _prdRunRepository.findApproval(workflowKey);
  }
}
