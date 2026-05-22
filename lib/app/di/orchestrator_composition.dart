import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:pulse_ai/app/di/hive_bootstrap.dart';
import 'package:pulse_ai/features/orchestrator/data/hive/orchestrator_hive_boxes.dart';
import 'package:pulse_ai/features/orchestrator/data/recent_projects_local_storage.dart';
import 'package:pulse_ai/features/orchestrator/data/repositories/artifact_repository_impl.dart';
import 'package:pulse_ai/features/orchestrator/data/repositories/prd_run_repository_impl.dart';
import 'package:pulse_ai/features/orchestrator/data/repositories/recent_projects_repository_impl.dart';
import 'package:pulse_ai/features/orchestrator/data/repositories/workflow_repository_impl.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/artifact_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/prd_run_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/recent_projects_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/workflow_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/artifact_persistence_service.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/cursor_credential_store_service.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/cursor_prd_agent_service.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/local_git_branches_service.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/local_git_origin_remote_service.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/prd_run_completion_output_source.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/prd_run_connection_gate.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/project_sandbox_access_service.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/append_stream_event_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/approve_prd_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/build_prd_run_context_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/cancel_prd_agent_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/complete_prd_agent_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/create_workflow_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/fail_prd_agent_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/find_prd_approval_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/import_local_project_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_local_git_branches_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_recent_projects_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_workflow_adrs_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_workflows_by_project_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/read_prd_markdown_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/reconcile_prd_run_status_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/reject_prd_with_feedback_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/remove_cursor_credential_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/restore_last_finalized_prd_session_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/run_cursor_connection_preflight_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/save_cursor_credential_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/save_prd_draft_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/select_active_project_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/start_prd_agent_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/validate_cursor_credential_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/import_flow_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/initialize_agent_branches_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/orchestrator_main_content_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_adr_list_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_review_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_workflow_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/recent_projects_cubit.dart';
import 'package:pulse_ai/features/orchestrator/service/cursor_cloud_agent_http_client_impl.dart';
import 'package:pulse_ai/features/orchestrator/service/cursor_credential_store_service_impl.dart';
import 'package:pulse_ai/features/orchestrator/service/cursor_prd_agent_service_impl.dart';
import 'package:pulse_ai/features/orchestrator/service/default_prd_run_completion_output_source.dart';
import 'package:pulse_ai/features/orchestrator/service/filesystem_artifact_service_impl.dart';
import 'package:pulse_ai/features/orchestrator/service/local_directory_picker_service_impl.dart';
import 'package:pulse_ai/features/orchestrator/service/local_git_branches_service_impl.dart';
import 'package:pulse_ai/features/orchestrator/service/local_git_origin_remote_service_impl.dart';
import 'package:pulse_ai/features/orchestrator/service/project_sandbox_access_service_impl.dart';
import 'package:shared_preferences/shared_preferences.dart';

final class PrdWorkspaceCubitBundle {
  PrdWorkspaceCubitBundle({
    required this.workflowCubit,
    required this.reviewCubit,
    required this.adrListCubit,
  });

  final PrdWorkflowCubit workflowCubit;
  final PrdReviewCubit reviewCubit;
  final PrdAdrListCubit adrListCubit;

  void dispose() {
    unawaited(workflowCubit.close());
    unawaited(reviewCubit.close());
    unawaited(adrListCubit.close());
  }
}

final class OrchestratorComposition {
  OrchestratorComposition({
    required this.recentProjectsRepository,
    required this.artifactRepository,
    required this.workflowRepository,
    required this.prdRunRepository,
    required this.createWorkflowUseCase,
    required this.listWorkflowsByProjectUseCase,
    required this.savePrdDraftUseCase,
    required this.readPrdMarkdownUseCase,
    required this.listWorkflowAdrsUseCase,
    required this.startPrdAgentRunUseCase,
    required this.approvePrdUseCase,
    required this.rejectPrdWithFeedbackUseCase,
    required this.appendStreamEventUseCase,
    required this.completePrdAgentRunUseCase,
    required this.cancelPrdAgentRunUseCase,
    required this.failPrdAgentRunUseCase,
    required this.restoreLastFinalizedPrdSessionUseCase,
    required this.reconcilePrdRunStatusUseCase,
    required this.cursorPrdAgentService,
    required this.runCursorConnectionPreflightUseCase,
    required this.prdRunCompletionOutputSource,
    required this.recentProjectsCubit,
    required this.importFlowCubit,
    required this.initializeAgentBranchesCubit,
    required this.orchestratorMainContentCubit,
    required this.cursorConnectionCubit,
  });

  final RecentProjectsRepository recentProjectsRepository;
  final ArtifactRepository artifactRepository;
  final WorkflowRepository workflowRepository;
  final PrdRunRepository prdRunRepository;
  final CreateWorkflowUseCase createWorkflowUseCase;
  final ListWorkflowsByProjectUseCase listWorkflowsByProjectUseCase;
  final SavePrdDraftUseCase savePrdDraftUseCase;
  final ReadPrdMarkdownUseCase readPrdMarkdownUseCase;
  final ListWorkflowAdrsUseCase listWorkflowAdrsUseCase;
  final StartPrdAgentRunUseCase startPrdAgentRunUseCase;
  final ApprovePrdUseCase approvePrdUseCase;
  final RejectPrdWithFeedbackUseCase rejectPrdWithFeedbackUseCase;
  final AppendStreamEventUseCase appendStreamEventUseCase;
  final CompletePrdAgentRunUseCase completePrdAgentRunUseCase;
  final CancelPrdAgentRunUseCase cancelPrdAgentRunUseCase;
  final FailPrdAgentRunUseCase failPrdAgentRunUseCase;
  final RestoreLastFinalizedPrdSessionUseCase
  restoreLastFinalizedPrdSessionUseCase;
  final ReconcilePrdRunStatusUseCase reconcilePrdRunStatusUseCase;
  final CursorPrdAgentService cursorPrdAgentService;
  final RunCursorConnectionPreflightUseCase runCursorConnectionPreflightUseCase;
  final PrdRunCompletionOutputSource prdRunCompletionOutputSource;
  final RecentProjectsCubit recentProjectsCubit;
  final ImportFlowCubit importFlowCubit;
  final InitializeAgentBranchesCubit initializeAgentBranchesCubit;
  final OrchestratorMainContentCubit orchestratorMainContentCubit;
  final CursorConnectionCubit cursorConnectionCubit;

  static Future<OrchestratorComposition> create() async {
    await HiveBootstrap.ensureInitialized();
    final SharedPreferences preferences = await SharedPreferences.getInstance();
    final RecentProjectsLocalStorage storage = RecentProjectsLocalStorage(
      preferences,
    );
    final RecentProjectsRepository repository = RecentProjectsRepositoryImpl(
      storage,
    );
    final LocalDirectoryPickerServiceImpl pickerService =
        LocalDirectoryPickerServiceImpl();

    final ListRecentProjectsUseCase listRecentProjectsUseCase =
        ListRecentProjectsUseCase(repository);
    final SelectActiveProjectUseCase selectActiveProjectUseCase =
        SelectActiveProjectUseCase(repository);
    final ProjectSandboxAccessService sandboxAccessService =
        ProjectSandboxAccessServiceImpl();
    final ImportLocalProjectUseCase importLocalProjectUseCase =
        ImportLocalProjectUseCase(
          repository: repository,
          pickerService: pickerService,
          sandboxAccessService: sandboxAccessService,
        );

    final ImportFlowCubit importFlowCubit = ImportFlowCubit(
      importLocalProjectUseCase: importLocalProjectUseCase,
    );

    final LocalGitBranchesService localGitBranchesService =
        LocalGitBranchesServiceImpl(sandboxAccessService: sandboxAccessService);
    final ListLocalGitBranchesUseCase listLocalGitBranchesUseCase =
        ListLocalGitBranchesUseCase(service: localGitBranchesService);
    final LocalGitOriginRemoteService localGitOriginRemoteService =
        LocalGitOriginRemoteServiceImpl(
          sandboxAccessService: sandboxAccessService,
        );
    final InitializeAgentBranchesCubit initializeAgentBranchesCubit =
        InitializeAgentBranchesCubit(
          listLocalGitBranchesUseCase: listLocalGitBranchesUseCase,
        );
    final OrchestratorMainContentCubit orchestratorMainContentCubit =
        OrchestratorMainContentCubit();

    final ArtifactPersistenceService artifactPersistenceService =
        await FilesystemArtifactServiceImpl.createFromApplicationSupport();
    final ArtifactRepository artifactRepository = ArtifactRepositoryImpl(
      artifactPersistenceService: artifactPersistenceService,
    );

    final OrchestratorHiveBoxes hiveBoxes = await OrchestratorHiveBoxes.open();
    final WorkflowRepository workflowRepository = WorkflowRepositoryImpl(
      boxes: hiveBoxes,
      artifactPersistenceService: artifactPersistenceService,
    );
    final PrdRunRepository prdRunRepository = PrdRunRepositoryImpl(
      boxes: hiveBoxes,
    );

    final CreateWorkflowUseCase createWorkflowUseCase = CreateWorkflowUseCase(
      workflowRepository: workflowRepository,
    );
    final ListWorkflowsByProjectUseCase listWorkflowsByProjectUseCase =
        ListWorkflowsByProjectUseCase(workflowRepository);

    final RecentProjectsCubit recentProjectsCubit = RecentProjectsCubit(
      listRecentProjectsUseCase: listRecentProjectsUseCase,
      selectActiveProjectUseCase: selectActiveProjectUseCase,
      listWorkflowsByProjectUseCase: listWorkflowsByProjectUseCase,
    );

    final SavePrdDraftUseCase savePrdDraftUseCase = SavePrdDraftUseCase(
      artifactRepository: artifactRepository,
      prdRunRepository: prdRunRepository,
    );
    final ReadPrdMarkdownUseCase readPrdMarkdownUseCase =
        ReadPrdMarkdownUseCase(artifactRepository);
    final ListWorkflowAdrsUseCase listWorkflowAdrsUseCase =
        ListWorkflowAdrsUseCase(artifactRepository);

    final BuildPrdRunContextUseCase buildPrdRunContextUseCase =
        BuildPrdRunContextUseCase(
          recentProjectsRepository: repository,
          listLocalGitBranchesUseCase: listLocalGitBranchesUseCase,
          localGitOriginRemoteService: localGitOriginRemoteService,
        );

    final CursorCredentialStoreService cursorCredentialStoreService =
        CursorCredentialStoreServiceImpl();
    final CursorCloudAgentHttpClientImpl cursorCloudAgentHttpClient =
        CursorCloudAgentHttpClientImpl(
          credentialStore: cursorCredentialStoreService,
        );
    final CursorPrdAgentService cursorPrdAgentService =
        CursorPrdAgentServiceImpl(
          credentialStore: cursorCredentialStoreService,
          httpClient: cursorCloudAgentHttpClient,
        );
    final RunCursorConnectionPreflightUseCase
    runCursorConnectionPreflightUseCase = RunCursorConnectionPreflightUseCase(
      cursorPrdAgentService: cursorPrdAgentService,
    );
    final ValidateCursorCredentialUseCase validateCursorCredentialUseCase =
        ValidateCursorCredentialUseCase(
          cursorPrdAgentService: cursorPrdAgentService,
        );
    final SaveCursorCredentialUseCase saveCursorCredentialUseCase =
        SaveCursorCredentialUseCase(
          credentialStore: cursorCredentialStoreService,
        );
    final RemoveCursorCredentialUseCase removeCursorCredentialUseCase =
        RemoveCursorCredentialUseCase(
          credentialStore: cursorCredentialStoreService,
        );
    final CursorConnectionCubit cursorConnectionCubit = CursorConnectionCubit(
      runCursorConnectionPreflightUseCase: runCursorConnectionPreflightUseCase,
      validateCursorCredentialUseCase: validateCursorCredentialUseCase,
      saveCursorCredentialUseCase: saveCursorCredentialUseCase,
      removeCursorCredentialUseCase: removeCursorCredentialUseCase,
    );

    final PreflightPrdRunConnectionGate prdRunConnectionGate =
        PreflightPrdRunConnectionGate(
          preflight: runCursorConnectionPreflightUseCase.call,
        );
    final StartPrdAgentRunUseCase startPrdAgentRunUseCase =
        StartPrdAgentRunUseCase(
          connectionGate: prdRunConnectionGate,
          buildPrdRunContextUseCase: buildPrdRunContextUseCase,
          prdRunRepository: prdRunRepository,
          workflowRepository: workflowRepository,
          cursorPrdAgentService: cursorPrdAgentService,
        );
    final ApprovePrdUseCase approvePrdUseCase = ApprovePrdUseCase(
      prdRunRepository: prdRunRepository,
      workflowRepository: workflowRepository,
    );
    final RejectPrdWithFeedbackUseCase rejectPrdWithFeedbackUseCase =
        RejectPrdWithFeedbackUseCase(
          prdRunRepository: prdRunRepository,
          workflowRepository: workflowRepository,
          startPrdAgentRunUseCase: startPrdAgentRunUseCase,
        );
    final AppendStreamEventUseCase appendStreamEventUseCase =
        AppendStreamEventUseCase(
          prdRunRepository: prdRunRepository,
          artifactRepository: artifactRepository,
        );
    final CompletePrdAgentRunUseCase completePrdAgentRunUseCase =
        CompletePrdAgentRunUseCase(
          prdRunRepository: prdRunRepository,
          workflowRepository: workflowRepository,
          artifactRepository: artifactRepository,
        );
    final CancelPrdAgentRunUseCase cancelPrdAgentRunUseCase =
        CancelPrdAgentRunUseCase(
          prdRunRepository: prdRunRepository,
          workflowRepository: workflowRepository,
          cursorPrdAgentService: cursorPrdAgentService,
        );
    final FailPrdAgentRunUseCase failPrdAgentRunUseCase =
        FailPrdAgentRunUseCase(
          prdRunRepository: prdRunRepository,
          workflowRepository: workflowRepository,
        );
    final RestoreLastFinalizedPrdSessionUseCase
    restoreLastFinalizedPrdSessionUseCase =
        RestoreLastFinalizedPrdSessionUseCase(
          prdRunRepository: prdRunRepository,
        );
    final ReconcilePrdRunStatusUseCase reconcilePrdRunStatusUseCase =
        ReconcilePrdRunStatusUseCase(
          credentialStore: cursorCredentialStoreService,
          cursorPrdAgentService: cursorPrdAgentService,
          prdRunRepository: prdRunRepository,
          workflowRepository: workflowRepository,
        );
    const PrdRunCompletionOutputSource prdRunCompletionOutputSource =
        DefaultPrdRunCompletionOutputSource();

    return OrchestratorComposition(
      recentProjectsRepository: repository,
      artifactRepository: artifactRepository,
      workflowRepository: workflowRepository,
      prdRunRepository: prdRunRepository,
      createWorkflowUseCase: createWorkflowUseCase,
      listWorkflowsByProjectUseCase: listWorkflowsByProjectUseCase,
      savePrdDraftUseCase: savePrdDraftUseCase,
      readPrdMarkdownUseCase: readPrdMarkdownUseCase,
      listWorkflowAdrsUseCase: listWorkflowAdrsUseCase,
      startPrdAgentRunUseCase: startPrdAgentRunUseCase,
      approvePrdUseCase: approvePrdUseCase,
      rejectPrdWithFeedbackUseCase: rejectPrdWithFeedbackUseCase,
      appendStreamEventUseCase: appendStreamEventUseCase,
      completePrdAgentRunUseCase: completePrdAgentRunUseCase,
      cancelPrdAgentRunUseCase: cancelPrdAgentRunUseCase,
      failPrdAgentRunUseCase: failPrdAgentRunUseCase,
      restoreLastFinalizedPrdSessionUseCase:
          restoreLastFinalizedPrdSessionUseCase,
      reconcilePrdRunStatusUseCase: reconcilePrdRunStatusUseCase,
      cursorPrdAgentService: cursorPrdAgentService,
      runCursorConnectionPreflightUseCase: runCursorConnectionPreflightUseCase,
      prdRunCompletionOutputSource: prdRunCompletionOutputSource,
      recentProjectsCubit: recentProjectsCubit,
      importFlowCubit: importFlowCubit,
      initializeAgentBranchesCubit: initializeAgentBranchesCubit,
      orchestratorMainContentCubit: orchestratorMainContentCubit,
      cursorConnectionCubit: cursorConnectionCubit,
    );
  }

  PrdWorkspaceCubitBundle createPrdWorkspaceCubitBundle() {
    return PrdWorkspaceCubitBundle(
      workflowCubit: PrdWorkflowCubit(
        startPrdAgentRunUseCase: startPrdAgentRunUseCase,
        appendStreamEventUseCase: appendStreamEventUseCase,
        completePrdAgentRunUseCase: completePrdAgentRunUseCase,
        cancelPrdAgentRunUseCase: cancelPrdAgentRunUseCase,
        failPrdAgentRunUseCase: failPrdAgentRunUseCase,
        restoreLastFinalizedPrdSessionUseCase:
            restoreLastFinalizedPrdSessionUseCase,
        reconcilePrdRunStatusUseCase: reconcilePrdRunStatusUseCase,
        prdRunRepository: prdRunRepository,
        cursorPrdAgentService: cursorPrdAgentService,
        completionOutputSource: prdRunCompletionOutputSource,
      ),
      reviewCubit: PrdReviewCubit(
        readPrdMarkdownUseCase: readPrdMarkdownUseCase,
        savePrdDraftUseCase: savePrdDraftUseCase,
        approvePrdUseCase: approvePrdUseCase,
        rejectPrdWithFeedbackUseCase: rejectPrdWithFeedbackUseCase,
        findPrdApprovalUseCase: FindPrdApprovalUseCase(prdRunRepository),
        runCursorConnectionPreflightUseCase:
            runCursorConnectionPreflightUseCase,
      ),
      adrListCubit: PrdAdrListCubit(
        listWorkflowAdrsUseCase: listWorkflowAdrsUseCase,
      ),
    );
  }

  void dispose() {
    unawaited(recentProjectsCubit.close());
    unawaited(importFlowCubit.close());
    unawaited(initializeAgentBranchesCubit.close());
    unawaited(orchestratorMainContentCubit.close());
    unawaited(cursorConnectionCubit.close());
  }
}

class OrchestratorCompositionScope extends StatefulWidget {
  const OrchestratorCompositionScope({required this.child, super.key});

  final Widget child;

  @override
  State<OrchestratorCompositionScope> createState() =>
      _OrchestratorCompositionScopeState();
}

class _OrchestratorCompositionScopeState
    extends State<OrchestratorCompositionScope> {
  late final Future<OrchestratorComposition> _compositionFuture =
      OrchestratorComposition.create();
  OrchestratorComposition? _composition;

  @override
  void dispose() {
    _composition?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<OrchestratorComposition>(
      future: _compositionFuture,
      builder:
          (
            BuildContext context,
            AsyncSnapshot<OrchestratorComposition> snapshot,
          ) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const SizedBox.shrink();
            }

            if (!snapshot.hasData) {
              return const SizedBox.shrink();
            }

            _composition ??= snapshot.data!;
            final OrchestratorComposition composition = _composition!;

            return MultiRepositoryProvider(
              providers: <RepositoryProvider<dynamic>>[
                RepositoryProvider<OrchestratorComposition>.value(
                  value: composition,
                ),
                RepositoryProvider<RecentProjectsRepository>.value(
                  value: composition.recentProjectsRepository,
                ),
                RepositoryProvider<ArtifactRepository>.value(
                  value: composition.artifactRepository,
                ),
                RepositoryProvider<WorkflowRepository>.value(
                  value: composition.workflowRepository,
                ),
                RepositoryProvider<PrdRunRepository>.value(
                  value: composition.prdRunRepository,
                ),
              ],
              child: MultiBlocProvider(
                providers: <BlocProvider<dynamic>>[
                  BlocProvider<RecentProjectsCubit>.value(
                    value: composition.recentProjectsCubit,
                  ),
                  BlocProvider<ImportFlowCubit>.value(
                    value: composition.importFlowCubit,
                  ),
                  BlocProvider<InitializeAgentBranchesCubit>.value(
                    value: composition.initializeAgentBranchesCubit,
                  ),
                  BlocProvider<OrchestratorMainContentCubit>.value(
                    value: composition.orchestratorMainContentCubit,
                  ),
                  BlocProvider<CursorConnectionCubit>.value(
                    value: composition.cursorConnectionCubit,
                  ),
                ],
                child: widget.child,
              ),
            );
          },
    );
  }
}
