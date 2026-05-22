import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/cursor_connection_failure.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/fakes/fake_artifact_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/fakes/fake_prd_run_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/fakes/fake_workflow_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/prd_run_connection_gate.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/approve_prd_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/build_prd_run_context_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/find_prd_approval_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_local_git_branches_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/read_prd_markdown_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/reject_prd_with_feedback_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/run_cursor_connection_preflight_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/save_prd_draft_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/start_prd_agent_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_review_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_review_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_review_load_status.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_artifact_presentation.dart';
import 'package:pulse_ai/features/orchestrator/service/fakes/fake_cursor_prd_agent_service.dart';

import '../../domain/usecases/fake_cursor_prd_agent_service.dart'
    as lifecycle_fake;
import '../../domain/usecases/fake_local_git_branches_service.dart';
import '../../domain/usecases/fake_recent_projects_repository.dart';

void main() {
  const String projectId = '550e8400-e29b-41d4-a716-446655440000';
  const String slug = 'payments-api';
  const String repoPath = '/Users/dev/repo';
  const String branchName = 'main';
  const String workflowKey = '$projectId::$slug';
  const String draftMarkdown = '# PRD\n\nInitial agent draft.';
  const String editedMarkdown = '# PRD\n\nUser edited body.';

  late FakeArtifactRepository artifactRepository;
  late FakePrdRunRepository prdRunRepository;
  late FakeWorkflowRepository workflowRepository;
  late FakeRecentProjectsRepository projectsRepository;
  late FakeLocalGitBranchesService gitService;
  late FakeCursorPrdAgentService cursorService;
  late lifecycle_fake.FakeCursorPrdAgentServiceForLifecycle rejectAgentService;
  late SavePrdDraftUseCase savePrdDraftUseCase;
  late ReadPrdMarkdownUseCase readPrdMarkdownUseCase;
  late FindPrdApprovalUseCase findPrdApprovalUseCase;
  late ApprovePrdUseCase approvePrdUseCase;
  late RejectPrdWithFeedbackUseCase rejectPrdWithFeedbackUseCase;
  late RunCursorConnectionPreflightUseCase preflightUseCase;
  late StartPrdAgentRunUseCase startPrdAgentRunUseCase;
  late String sourceRunId;

  PrdReviewCubit buildCubit() {
    return PrdReviewCubit(
      readPrdMarkdownUseCase: readPrdMarkdownUseCase,
      savePrdDraftUseCase: savePrdDraftUseCase,
      approvePrdUseCase: approvePrdUseCase,
      rejectPrdWithFeedbackUseCase: rejectPrdWithFeedbackUseCase,
      findPrdApprovalUseCase: findPrdApprovalUseCase,
      runCursorConnectionPreflightUseCase: preflightUseCase,
    );
  }

  Future<void> seedReviewableDraft() async {
    artifactRepository.prdMarkdownByKey[workflowKey] = draftMarkdown;
    final Either<Failure, PrdRunEntity> runResult = await prdRunRepository
        .createRun(
          workflowKey: workflowKey,
          status: PrdRunStatus.completed,
          cloudRunId: 'cloud-1',
        );
    sourceRunId = runResult.getRight().toNullable()!.id;
    await prdRunRepository.upsertApproval(
      workflowKey: workflowKey,
      status: PrdApprovalStatus.pendingApproval,
      sourceRunId: sourceRunId,
    );
  }

  setUp(() async {
    artifactRepository = FakeArtifactRepository();
    prdRunRepository = FakePrdRunRepository();
    workflowRepository = FakeWorkflowRepository();
    projectsRepository = FakeRecentProjectsRepository();
    gitService = FakeLocalGitBranchesService();
    cursorService = FakeCursorPrdAgentService();
    rejectAgentService = lifecycle_fake.FakeCursorPrdAgentServiceForLifecycle();
    preflightUseCase = RunCursorConnectionPreflightUseCase(
      cursorPrdAgentService: cursorService,
    );
    savePrdDraftUseCase = SavePrdDraftUseCase(
      artifactRepository: artifactRepository,
      prdRunRepository: prdRunRepository,
      clock: () => DateTime.utc(2026, 5, 21, 16),
    );
    readPrdMarkdownUseCase = ReadPrdMarkdownUseCase(artifactRepository);
    findPrdApprovalUseCase = FindPrdApprovalUseCase(prdRunRepository);
    approvePrdUseCase = ApprovePrdUseCase(
      prdRunRepository: prdRunRepository,
      workflowRepository: workflowRepository,
      clock: () => DateTime.utc(2026, 5, 21, 16),
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
      branches: <String>[branchName],
      headBranchName: branchName,
    );
    final BuildPrdRunContextUseCase buildContextUseCase =
        BuildPrdRunContextUseCase(
          recentProjectsRepository: projectsRepository,
          listLocalGitBranchesUseCase: ListLocalGitBranchesUseCase(
            service: gitService,
          ),
        );
    startPrdAgentRunUseCase = StartPrdAgentRunUseCase(
      connectionGate: PreflightPrdRunConnectionGate(
        preflight: () async => right(null),
      ),
      buildPrdRunContextUseCase: buildContextUseCase,
      prdRunRepository: prdRunRepository,
      workflowRepository: workflowRepository,
      cursorPrdAgentService: rejectAgentService,
      clock: () => DateTime.utc(2026, 5, 21, 16),
    );
    rejectPrdWithFeedbackUseCase = RejectPrdWithFeedbackUseCase(
      prdRunRepository: prdRunRepository,
      workflowRepository: workflowRepository,
      startPrdAgentRunUseCase: startPrdAgentRunUseCase,
    );

    await workflowRepository.create(
      projectId: projectId,
      slug: slug,
      branchName: branchName,
    );
    await workflowRepository.update(
      (await workflowRepository.findBySlug(
        projectId: projectId,
        slug: slug,
      ))!.copyWith(prdPhaseStatus: PrdPhaseStatus.pendingApproval),
    );
    await seedReviewableDraft();
  });

  group('PrdReviewCubit', () {
    blocTest<PrdReviewCubit, PrdReviewState>(
      'load draft populates editor text from fake repo',
      build: buildCubit,
      act: (PrdReviewCubit cubit) async {
        cubit.bindReviewContext(
          projectId: projectId,
          slug: slug,
          repoPath: repoPath,
          branchName: branchName,
        );
        await cubit.loadDraft();
      },
      verify: (PrdReviewCubit cubit) {
        expect(cubit.state.loadStatus, PrdReviewLoadStatus.ready);
        expect(cubit.editorText.value, draftMarkdown);
        expect(cubit.state.savedMarkdown, draftMarkdown);
        expect(cubit.state.isDirty, isFalse);
        expect(cubit.state.sourceRunId, sourceRunId);
      },
    );

    blocTest<PrdReviewCubit, PrdReviewState>(
      'save draft clears dirty flag and persists markdown once',
      build: buildCubit,
      act: (PrdReviewCubit cubit) async {
        cubit.bindReviewContext(
          projectId: projectId,
          slug: slug,
          repoPath: repoPath,
          branchName: branchName,
        );
        await cubit.loadDraft();
        cubit.editorText.value = editedMarkdown;
        cubit.onEditorTextChanged(editedMarkdown);
        await cubit.saveDraft();
      },
      verify: (PrdReviewCubit cubit) async {
        expect(cubit.state.isDirty, isFalse);
        expect(cubit.state.savedMarkdown, editedMarkdown);
        expect(
          artifactRepository.prdMarkdownByKey[workflowKey],
          editedMarkdown,
        );
        final PrdApprovalEntity? approval = await prdRunRepository.findApproval(
          workflowKey,
        );
        expect(approval?.lastEditedAt, isNotNull);
      },
    );

    blocTest<PrdReviewCubit, PrdReviewState>(
      'approve persists current editor text then approves workflow',
      build: buildCubit,
      act: (PrdReviewCubit cubit) async {
        cursorService.nextPreflightResult = right(null);
        cubit.bindReviewContext(
          projectId: projectId,
          slug: slug,
          repoPath: repoPath,
          branchName: branchName,
        );
        await cubit.loadDraft();
        cubit.editorText.value = editedMarkdown;
        cubit.onEditorTextChanged(editedMarkdown);
        await cubit.approve();
      },
      verify: (PrdReviewCubit cubit) async {
        expect(cubit.state.isApproved, isTrue);
        expect(
          artifactRepository.prdMarkdownByKey[workflowKey],
          editedMarkdown,
        );
        final PrdApprovalEntity? approval = await prdRunRepository.findApproval(
          workflowKey,
        );
        expect(approval?.status, PrdApprovalStatus.approved);
        final WorkflowEntity? workflow = await workflowRepository.findBySlug(
          projectId: projectId,
          slug: slug,
        );
        expect(workflow?.prdPhaseStatus, PrdPhaseStatus.approved);
      },
    );

    blocTest<PrdReviewCubit, PrdReviewState>(
      'reject with feedback invokes reject use case and starts rerun',
      build: buildCubit,
      act: (PrdReviewCubit cubit) async {
        rejectAgentService.startRunCallCount = 0;
        cubit.bindReviewContext(
          projectId: projectId,
          slug: slug,
          repoPath: repoPath,
          branchName: branchName,
        );
        await cubit.loadDraft();
        await cubit.rejectWithFeedback('add security');
      },
      verify: (PrdReviewCubit cubit) async {
        expect(rejectAgentService.startRunCallCount, 1);
        final PrdRunEntity? rejected = await prdRunRepository.findRunById(
          sourceRunId,
        );
        expect(rejected?.feedback, 'add security');
        expect(cubit.state.loadStatus, PrdReviewLoadStatus.unavailable);
        expect(rejectAgentService.lastStartContext?.feedback, 'add security');
      },
    );

    blocTest<PrdReviewCubit, PrdReviewState>(
      'dirty guard emits mustConfirmOverwrite before replacing editor text',
      build: buildCubit,
      act: (PrdReviewCubit cubit) async {
        cubit.bindReviewContext(
          projectId: projectId,
          slug: slug,
          repoPath: repoPath,
          branchName: branchName,
        );
        await cubit.loadDraft();
        cubit.editorText.value = editedMarkdown;
        cubit.onEditorTextChanged(editedMarkdown);
        cubit.applyIncomingDraft('# PRD\n\nNew agent draft.');
      },
      verify: (PrdReviewCubit cubit) {
        expect(cubit.state.isDirty, isTrue);
        expect(cubit.state.mustConfirmOverwrite, isTrue);
        expect(
          cubit.state.pendingOverwriteMarkdown,
          '# PRD\n\nNew agent draft.',
        );
        expect(cubit.editorText.value, editedMarkdown);
      },
    );

    blocTest<PrdReviewCubit, PrdReviewState>(
      'confirm overwrite replaces editor text and clears dirty guard',
      build: buildCubit,
      act: (PrdReviewCubit cubit) async {
        cubit.bindReviewContext(
          projectId: projectId,
          slug: slug,
          repoPath: repoPath,
          branchName: branchName,
        );
        await cubit.loadDraft();
        cubit.editorText.value = editedMarkdown;
        cubit.onEditorTextChanged(editedMarkdown);
        cubit.applyIncomingDraft('# PRD\n\nNew agent draft.');
        cubit.confirmOverwriteIncomingDraft();
      },
      verify: (PrdReviewCubit cubit) {
        expect(cubit.state.mustConfirmOverwrite, isFalse);
        expect(cubit.state.isDirty, isFalse);
        expect(cubit.editorText.value, '# PRD\n\nNew agent draft.');
      },
    );

    blocTest<PrdReviewCubit, PrdReviewState>(
      'approve blocked when connection gate reports disconnected',
      build: buildCubit,
      act: (PrdReviewCubit cubit) async {
        cubit.bindReviewContext(
          projectId: projectId,
          slug: slug,
          repoPath: repoPath,
          branchName: branchName,
        );
        cubit.syncConnectionGate(
          const CursorConnectionState(
            status: CursorConnectionStatus.disconnected,
            remediationMessage:
                OrchestratorStrings.cursorConnectionDisconnectedRemediation,
          ),
        );
        await cubit.loadDraft();
        await cubit.approve();
      },
      verify: (PrdReviewCubit cubit) async {
        expect(cubit.state.isApproved, isFalse);
        expect(cubit.state.isApproveBlocked, isTrue);
        expect(
          cubit.state.approveBlockedMessageKey,
          OrchestratorStrings.cursorConnectionDisconnectedRemediation,
        );
        final PrdApprovalEntity? approval = await prdRunRepository.findApproval(
          workflowKey,
        );
        expect(approval?.status, PrdApprovalStatus.pendingApproval);
      },
    );

    blocTest<PrdReviewCubit, PrdReviewState>(
      'approve blocked when preflight fails at review time',
      build: buildCubit,
      act: (PrdReviewCubit cubit) async {
        cursorService.nextPreflightResult = left(
          const CursorConnectionFailure.network(),
        );
        cubit.bindReviewContext(
          projectId: projectId,
          slug: slug,
          repoPath: repoPath,
          branchName: branchName,
        );
        await cubit.loadDraft();
        await cubit.approve();
      },
      verify: (PrdReviewCubit cubit) {
        expect(cubit.state.isApproved, isFalse);
        expect(cubit.state.isApproveBlocked, isTrue);
        expect(
          cubit.state.approveBlockedMessageKey,
          OrchestratorStrings.cursorConnectionDisconnectedRemediation,
        );
      },
    );

    blocTest<PrdReviewCubit, PrdReviewState>(
      'shows user edited badge after save when approval has lastEditedAt',
      build: buildCubit,
      act: (PrdReviewCubit cubit) async {
        cubit.bindReviewContext(
          projectId: projectId,
          slug: slug,
          repoPath: repoPath,
          branchName: branchName,
        );
        await cubit.loadDraft();
        cubit.editorText.value = editedMarkdown;
        cubit.onEditorTextChanged(editedMarkdown);
        await cubit.saveDraft();
      },
      verify: (PrdReviewCubit cubit) {
        expect(cubit.state.showsUserEditedBadge, isTrue);
      },
    );

    blocTest<PrdReviewCubit, PrdReviewState>(
      'load draft with missing artifact starts from empty editor',
      build: buildCubit,
      setUp: () async {
        artifactRepository.prdMarkdownByKey.remove(workflowKey);
      },
      act: (PrdReviewCubit cubit) async {
        cubit.bindReviewContext(
          projectId: projectId,
          slug: slug,
          repoPath: repoPath,
          branchName: branchName,
        );
        await cubit.loadDraft();
      },
      verify: (PrdReviewCubit cubit) {
        expect(cubit.state.loadStatus, PrdReviewLoadStatus.ready);
        expect(cubit.editorText.value, isEmpty);
        expect(
          cubit.state.failureMessageKey,
          PrdArtifactFailureMessageKeys.missingArtifact,
        );
      },
    );

    blocTest<PrdReviewCubit, PrdReviewState>(
      'load draft exposes sourceRunId for restored run alignment',
      build: buildCubit,
      act: (PrdReviewCubit cubit) async {
        cubit.bindReviewContext(
          projectId: projectId,
          slug: slug,
          repoPath: repoPath,
          branchName: branchName,
        );
        await cubit.loadDraft();
      },
      verify: (PrdReviewCubit cubit) {
        expect(cubit.state.sourceRunId, sourceRunId);
        expect(
          PrdArtifactPresentation.showsRestoredRunOnPrdCard(
            sourceRunId: cubit.state.sourceRunId,
            restoredRunId: sourceRunId,
          ),
          isTrue,
        );
      },
    );

    blocTest<PrdReviewCubit, PrdReviewState>(
      'load draft is unavailable when approval is already approved',
      build: buildCubit,
      setUp: () async {
        await prdRunRepository.upsertApproval(
          workflowKey: workflowKey,
          status: PrdApprovalStatus.approved,
          sourceRunId: sourceRunId,
          approvedAt: DateTime.utc(2026, 5, 21, 16),
        );
      },
      act: (PrdReviewCubit cubit) async {
        cubit.bindReviewContext(
          projectId: projectId,
          slug: slug,
          repoPath: repoPath,
          branchName: branchName,
        );
        await cubit.loadDraft();
      },
      verify: (PrdReviewCubit cubit) {
        expect(cubit.state.loadStatus, PrdReviewLoadStatus.unavailable);
      },
    );

    blocTest<PrdReviewCubit, PrdReviewState>(
      'apply incoming draft without dirty replaces editor immediately',
      build: buildCubit,
      act: (PrdReviewCubit cubit) async {
        cubit.bindReviewContext(
          projectId: projectId,
          slug: slug,
          repoPath: repoPath,
          branchName: branchName,
        );
        await cubit.loadDraft();
        cubit.applyIncomingDraft('# PRD\n\nReplacement.');
      },
      verify: (PrdReviewCubit cubit) {
        expect(cubit.state.mustConfirmOverwrite, isFalse);
        expect(cubit.editorText.value, '# PRD\n\nReplacement.');
        expect(cubit.state.isDirty, isFalse);
      },
    );

    blocTest<PrdReviewCubit, PrdReviewState>(
      'cancel overwrite keeps dirty editor and clears guard',
      build: buildCubit,
      act: (PrdReviewCubit cubit) async {
        cubit.bindReviewContext(
          projectId: projectId,
          slug: slug,
          repoPath: repoPath,
          branchName: branchName,
        );
        await cubit.loadDraft();
        cubit.editorText.value = editedMarkdown;
        cubit.onEditorTextChanged(editedMarkdown);
        cubit.applyIncomingDraft('# PRD\n\nNew agent draft.');
        cubit.cancelOverwriteIncomingDraft();
      },
      verify: (PrdReviewCubit cubit) {
        expect(cubit.state.mustConfirmOverwrite, isFalse);
        expect(cubit.state.isDirty, isTrue);
        expect(cubit.editorText.value, editedMarkdown);
      },
    );

    blocTest<PrdReviewCubit, PrdReviewState>(
      'reject does nothing when feedback is empty',
      build: buildCubit,
      act: (PrdReviewCubit cubit) async {
        rejectAgentService.startRunCallCount = 0;
        cubit.bindReviewContext(
          projectId: projectId,
          slug: slug,
          repoPath: repoPath,
          branchName: branchName,
        );
        await cubit.loadDraft();
        await cubit.rejectWithFeedback('   ');
      },
      verify: (PrdReviewCubit cubit) {
        expect(rejectAgentService.startRunCallCount, 0);
        expect(cubit.state.loadStatus, PrdReviewLoadStatus.ready);
      },
    );
  });
}
