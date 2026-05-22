import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/cursor_connection_failure.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/cloud_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_reconcile_result.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_key.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/fakes/fake_prd_run_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/fakes/fake_workflow_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/reconcile_prd_run_status_use_case.dart';
import 'package:pulse_ai/features/orchestrator/service/cursor_cloud_run_id_codec.dart';
import 'package:pulse_ai/features/orchestrator/service/fakes/fake_cursor_prd_agent_service.dart';

import '../service/fakes/fake_cursor_credential_store_service.dart';

void main() {
  group('ReconcilePrdRunStatusUseCase', () {
    const String projectId = 'project-1';
    const String slug = 'agent-a';
    final String workflowKey = WorkflowKey.compose(
      projectId: projectId,
      slug: slug,
    );
    final String cloudRunId = CursorCloudRunIdCodec.encode(
      agentId: 'bc-agent-1',
      runId: 'run-agent-1',
    );

    late FakeCursorCredentialStoreService credentialStore;
    late FakeCursorPrdAgentService agentService;
    late FakePrdRunRepository prdRunRepository;
    late FakeWorkflowRepository workflowRepository;
    late ReconcilePrdRunStatusUseCase useCase;

    Future<PrdRunEntity> seedRunningRun() async {
      final Either<Failure, PrdRunEntity> created = await prdRunRepository
          .createRun(
            workflowKey: workflowKey,
            status: PrdRunStatus.running,
            cloudRunId: cloudRunId,
          );
      return created.getRight().toNullable()!;
    }

    setUp(() async {
      credentialStore = FakeCursorCredentialStoreService()
        ..storedCredential = 'cursor-api-key';
      agentService = FakeCursorPrdAgentService();
      prdRunRepository = FakePrdRunRepository();
      workflowRepository = FakeWorkflowRepository();
      useCase = ReconcilePrdRunStatusUseCase(
        credentialStore: credentialStore,
        cursorPrdAgentService: agentService,
        prdRunRepository: prdRunRepository,
        workflowRepository: workflowRepository,
        clock: () => DateTime.utc(2026, 5, 22, 12),
      );

      await workflowRepository.create(
        projectId: projectId,
        slug: slug,
        branchName: 'main',
      );
      final WorkflowEntity? workflow = await workflowRepository.findBySlug(
        projectId: projectId,
        slug: slug,
      );
      await workflowRepository.update(
        workflow!.copyWith(prdPhaseStatus: PrdPhaseStatus.running),
      );
    });

    test('skips cloud call when cloudRunId is missing', () async {
      final Either<Failure, PrdRunEntity> created = await prdRunRepository
          .createRun(workflowKey: workflowKey, status: PrdRunStatus.running);
      final PrdRunEntity run = created.getRight().toNullable()!;

      final Either<Failure, PrdRunReconcileResult> result = await useCase(run);

      expect(result.isRight(), isTrue);
      result.fold((_) => fail('expected right'), (PrdRunReconcileResult value) {
        expect(value.outcome, PrdRunReconcileOutcome.skippedNoCloudRunId);
      });
      expect(agentService.fetchRunStatusCallCount, 0);
    });

    test('skips cloud call when credential is missing', () async {
      credentialStore.storedCredential = null;
      final PrdRunEntity run = await seedRunningRun();

      final Either<Failure, PrdRunReconcileResult> result = await useCase(run);

      expect(result.isRight(), isTrue);
      result.fold((_) => fail('expected right'), (PrdRunReconcileResult value) {
        expect(value.outcome, PrdRunReconcileOutcome.skippedNoCredential);
      });
      expect(agentService.fetchRunStatusCallCount, 0);
      final PrdRunEntity? stored = await prdRunRepository.findRunById(run.id);
      expect(stored?.status, PrdRunStatus.running);
    });

    test('returns unchanged when cloud still reports running', () async {
      agentService.nextFetchRunStatusResult = right(
        const CloudRunStatus(mappedPrdRunStatus: PrdRunStatus.running),
      );
      final PrdRunEntity run = await seedRunningRun();

      final Either<Failure, PrdRunReconcileResult> result = await useCase(run);

      expect(result.isRight(), isTrue);
      result.fold((_) => fail('expected right'), (PrdRunReconcileResult value) {
        expect(value.outcome, PrdRunReconcileOutcome.unchanged);
      });
      final PrdRunEntity? stored = await prdRunRepository.findRunById(run.id);
      expect(stored?.status, PrdRunStatus.running);
      expect(stored?.endedAt, isNull);
    });

    test(
      'updates run and workflow phase when cloud reports completed',
      () async {
        agentService.nextFetchRunStatusResult = right(
          const CloudRunStatus(mappedPrdRunStatus: PrdRunStatus.completed),
        );
        final PrdRunEntity run = await seedRunningRun();

        final Either<Failure, PrdRunReconcileResult> result = await useCase(
          run,
        );

        expect(result.isRight(), isTrue);
        result.fold((_) => fail('expected right'), (
          PrdRunReconcileResult value,
        ) {
          expect(value.outcome, PrdRunReconcileOutcome.updated);
          expect(value.run?.status, PrdRunStatus.completed);
          expect(value.run?.endedAt, DateTime.utc(2026, 5, 22, 12));
        });
        expect(agentService.fetchRunStatusCallCount, 1);
        expect(agentService.lastFetchRunStatusCloudRunId, cloudRunId);

        final WorkflowEntity? workflow = await workflowRepository.findBySlug(
          projectId: projectId,
          slug: slug,
        );
        expect(workflow?.prdPhaseStatus, PrdPhaseStatus.pendingApproval);
      },
    );

    test('returns left failure on 401 without updating run status', () async {
      agentService.nextFetchRunStatusResult = left(
        const CursorConnectionFailure.unauthorized(),
      );
      final PrdRunEntity run = await seedRunningRun();

      final Either<Failure, PrdRunReconcileResult> result = await useCase(run);

      expect(result.isLeft(), isTrue);
      final PrdRunEntity? stored = await prdRunRepository.findRunById(run.id);
      expect(stored?.status, PrdRunStatus.running);
    });

    test('returns left failure on 404 without marking run completed', () async {
      agentService.nextFetchRunStatusResult = left(
        const PrdRunFailure.cloudRunNotFound(),
      );
      final PrdRunEntity run = await seedRunningRun();

      final Either<Failure, PrdRunReconcileResult> result = await useCase(run);

      expect(result.isLeft(), isTrue);
      result.fold((failure) {
        expect(failure, isA<PrdRunFailure>());
        expect(
          (failure as PrdRunFailure).code,
          PrdRunFailureCode.cloudRunNotFound,
        );
      }, (_) => fail('expected left'));
      final PrdRunEntity? stored = await prdRunRepository.findRunById(run.id);
      expect(stored?.status, PrdRunStatus.running);
    });
  });
}
