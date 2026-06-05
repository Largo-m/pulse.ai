import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_key.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/fakes/fake_prd_run_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/find_prd_approval_use_case.dart';

void main() {
  const String projectId = '550e8400-e29b-41d4-a716-446655440000';
  const String slug = 'payments-api';
  final String workflowKey = WorkflowKey.compose(
    projectId: projectId,
    slug: slug,
  );

  late FakePrdRunRepository prdRunRepository;
  late FindPrdApprovalUseCase useCase;

  setUp(() {
    prdRunRepository = FakePrdRunRepository();
    useCase = FindPrdApprovalUseCase(prdRunRepository);
  });

  test('returns null when approval does not exist', () async {
    final result = await useCase(projectId: projectId, slug: slug);

    expect(result, isNull);
  });

  test('returns approval when it exists for workflow key', () async {
    final Either<Failure, PrdRunEntity> runResult = await prdRunRepository
        .createRun(workflowKey: workflowKey, status: PrdRunStatus.completed);
    final String runId = runResult.getRight().toNullable()!.id;
    await prdRunRepository.upsertApproval(
      workflowKey: workflowKey,
      status: PrdApprovalStatus.pendingApproval,
      sourceRunId: runId,
    );

    final result = await useCase(projectId: projectId, slug: slug);

    expect(result?.status, PrdApprovalStatus.pendingApproval);
    expect(result?.sourceRunId, runId);
  });
}
