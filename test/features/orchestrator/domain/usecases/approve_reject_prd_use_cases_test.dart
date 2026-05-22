import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_key.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/fakes/fake_artifact_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/fakes/fake_prd_run_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/fakes/fake_workflow_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/prd_run_connection_gate.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/approve_prd_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/build_prd_run_context_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/complete_prd_agent_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_local_git_branches_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/reject_prd_with_feedback_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/save_prd_draft_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/start_prd_agent_run_use_case.dart';

import 'fake_cursor_prd_agent_service.dart';
import 'fake_local_git_branches_service.dart';
import 'fake_local_git_origin_remote_service.dart';
import 'fake_recent_projects_repository.dart';

void main() {
  const String projectId = '550e8400-e29b-41d4-a716-446655440000';
  const String slug = 'payments-api';
  const String repoPath = '/Users/dev/repo';
  final DateTime fixedNow = DateTime.utc(2026, 5, 21, 15);

  late FakeWorkflowRepository workflowRepository;
  late FakePrdRunRepository prdRunRepository;
  late FakeArtifactRepository artifactRepository;
  late FakeRecentProjectsRepository projectsRepository;
  late FakeLocalGitBranchesService gitService;
  late FakeCursorPrdAgentServiceForLifecycle agentService;
  late BuildPrdRunContextUseCase buildContextUseCase;
  late StartPrdAgentRunUseCase startPrdAgentRunUseCase;

  Future<String> seedPendingApprovalRun() async {
    await workflowRepository.create(
      projectId: projectId,
      slug: slug,
      branchName: 'main',
      directive: 'Build payments PRD',
    );
    await workflowRepository.update(
      (await workflowRepository.findBySlug(
        projectId: projectId,
        slug: slug,
      ))!.copyWith(prdPhaseStatus: PrdPhaseStatus.pendingApproval),
    );
    projectsRepository.projects.add(
      LocalProjectEntity(
        id: projectId,
        canonicalPath: repoPath,
        displayName: 'Repo',
        lastAccessedAt: DateTime.utc(2026, 5, 20),
      ),
    );
    gitService.resultsByPath[repoPath] = const LocalGitBranchesResult(
      LocalGitBranchesOutcome.success,
      branches: <String>['main'],
      headBranchName: 'main',
    );

    final Either<Failure, PrdRunEntity> runResult = await prdRunRepository
        .createRun(
          workflowKey: WorkflowKey.compose(projectId: projectId, slug: slug),
          status: PrdRunStatus.completed,
        );
    final String runId = runResult.getRight().toNullable()!.id;

    final CompletePrdAgentRunUseCase completeUseCase =
        CompletePrdAgentRunUseCase(
          prdRunRepository: prdRunRepository,
          workflowRepository: workflowRepository,
          artifactRepository: artifactRepository,
          clock: () => fixedNow,
        );
    await completeUseCase(
      runId: runId,
      projectId: projectId,
      slug: slug,
      output: FakeCursorPrdAgentServiceForLifecycle.sampleCompletionOutput,
    );
    return runId;
  }

  setUp(() {
    workflowRepository = FakeWorkflowRepository();
    prdRunRepository = FakePrdRunRepository();
    artifactRepository = FakeArtifactRepository();
    projectsRepository = FakeRecentProjectsRepository();
    gitService = FakeLocalGitBranchesService();
    agentService = FakeCursorPrdAgentServiceForLifecycle();
    buildContextUseCase = BuildPrdRunContextUseCase(
      recentProjectsRepository: projectsRepository,
      listLocalGitBranchesUseCase: ListLocalGitBranchesUseCase(
        service: gitService,
      ),
      localGitOriginRemoteService: FakeLocalGitOriginRemoteService(),
    );
    startPrdAgentRunUseCase = StartPrdAgentRunUseCase(
      connectionGate: PreflightPrdRunConnectionGate(
        preflight: () async => right(null),
      ),
      buildPrdRunContextUseCase: buildContextUseCase,
      prdRunRepository: prdRunRepository,
      workflowRepository: workflowRepository,
      cursorPrdAgentService: agentService,
      clock: () => fixedNow,
    );
  });

  group('ApprovePrdUseCase', () {
    test('sets workflow phase approved and approval approvedAt', () async {
      await seedPendingApprovalRun();

      final ApprovePrdUseCase useCase = ApprovePrdUseCase(
        prdRunRepository: prdRunRepository,
        workflowRepository: workflowRepository,
        clock: () => fixedNow,
      );

      final Either<Failure, PrdApprovalEntity> result = await useCase(
        projectId: projectId,
        slug: slug,
      );

      expect(result.isRight(), isTrue);
      final PrdApprovalEntity approval = result.getRight().toNullable()!;
      expect(approval.status, PrdApprovalStatus.approved);
      expect(approval.approvedAt, fixedNow);

      final WorkflowEntity? workflow = await workflowRepository.findBySlug(
        projectId: projectId,
        slug: slug,
      );
      expect(workflow?.prdPhaseStatus, PrdPhaseStatus.approved);
    });

    test('does not invoke CursorPrdAgentService.startRun', () async {
      await seedPendingApprovalRun();
      agentService.startRunCallCount = 0;

      final ApprovePrdUseCase useCase = ApprovePrdUseCase(
        prdRunRepository: prdRunRepository,
        workflowRepository: workflowRepository,
        clock: () => fixedNow,
      );

      await useCase(projectId: projectId, slug: slug);

      expect(agentService.startRunCallCount, 0);
    });

    test('returns Left when workflow does not exist', () async {
      final ApprovePrdUseCase useCase = ApprovePrdUseCase(
        prdRunRepository: prdRunRepository,
        workflowRepository: workflowRepository,
      );

      final Either<Failure, PrdApprovalEntity> result = await useCase(
        projectId: projectId,
        slug: slug,
      );

      expect(result.isLeft(), isTrue);
      expect(
        (result.getLeft().toNullable() as PrdRunFailure).code,
        PrdRunFailureCode.workflowNotFound,
      );
    });

    test(
      'preserves lastEditedAt and sourceRunId after user-edited draft',
      () async {
        final String runId = await seedPendingApprovalRun();
        final DateTime editedAt = DateTime.utc(2026, 5, 21, 14);
        final SavePrdDraftUseCase saveUseCase = SavePrdDraftUseCase(
          artifactRepository: artifactRepository,
          prdRunRepository: prdRunRepository,
          clock: () => editedAt,
        );
        await saveUseCase(
          projectId: projectId,
          slug: slug,
          markdown: '# PRD editado',
        );

        final ApprovePrdUseCase useCase = ApprovePrdUseCase(
          prdRunRepository: prdRunRepository,
          workflowRepository: workflowRepository,
          clock: () => fixedNow,
        );

        final Either<Failure, PrdApprovalEntity> result = await useCase(
          projectId: projectId,
          slug: slug,
        );

        final PrdApprovalEntity approval = result.getRight().toNullable()!;
        expect(approval.lastEditedAt, editedAt);
        expect(approval.sourceRunId, runId);
        expect(approval.approvedAt, fixedNow);
      },
    );
  });

  group('RejectPrdWithFeedbackUseCase', () {
    test('returns Left when rejected run is unknown', () async {
      await seedPendingApprovalRun();

      final RejectPrdWithFeedbackUseCase useCase = RejectPrdWithFeedbackUseCase(
        prdRunRepository: prdRunRepository,
        workflowRepository: workflowRepository,
        startPrdAgentRunUseCase: startPrdAgentRunUseCase,
      );

      final Either<Failure, PrdRunEntity> result = await useCase(
        projectId: projectId,
        slug: slug,
        repoPath: repoPath,
        rejectedRunId: 'unknown-run-id',
        feedback: 'missing NFRs',
      );

      expect(result.isLeft(), isTrue);
      expect(agentService.startRunCallCount, 0);
    });

    test(
      'stores feedback on prior run and starts superseding run once',
      () async {
        final String rejectedRunId = await seedPendingApprovalRun();
        agentService.startRunCallCount = 0;

        final RejectPrdWithFeedbackUseCase useCase =
            RejectPrdWithFeedbackUseCase(
              prdRunRepository: prdRunRepository,
              workflowRepository: workflowRepository,
              startPrdAgentRunUseCase: startPrdAgentRunUseCase,
            );

        final Either<Failure, PrdRunEntity> result = await useCase(
          projectId: projectId,
          slug: slug,
          repoPath: repoPath,
          rejectedRunId: rejectedRunId,
          feedback: 'missing NFRs',
        );

        expect(result.isRight(), isTrue);
        expect(agentService.startRunCallCount, 1);

        final PrdRunEntity? priorRun = await prdRunRepository.findRunById(
          rejectedRunId,
        );
        expect(priorRun?.feedback, 'missing NFRs');

        final PrdRunEntity newRun = result.getRight().toNullable()!;
        expect(newRun.supersedesRunId, rejectedRunId);
        expect(newRun.feedback, 'missing NFRs');
        expect(newRun.status, PrdRunStatus.running);

        expect(agentService.lastStartContext?.feedback, 'missing NFRs');
        expect(agentService.lastStartContext?.supersedesRunId, rejectedRunId);

        final Either<Failure, List<PrdRunEntity>> runsResult =
            await prdRunRepository.listRunsForWorkflow(
              WorkflowKey.compose(projectId: projectId, slug: slug),
            );
        expect(runsResult.getRight().toNullable(), hasLength(2));

        final WorkflowEntity? workflow = await workflowRepository.findBySlug(
          projectId: projectId,
          slug: slug,
        );
        expect(workflow?.prdPhaseStatus, PrdPhaseStatus.running);
      },
    );
  });
}
