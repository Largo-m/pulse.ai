import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'package:pulse_ai/app/di/orchestrator_composition.dart';
import 'package:pulse_ai/app/router/route_paths.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/import_flow_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/import_flow_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/orchestrator_main_content_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/orchestrator_main_content_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/recent_projects_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/recent_projects_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/import_project_feedback.dart';
import 'package:pulse_ai/features/orchestrator/presentation/import_project_flow_outcome_handler.dart';
import 'package:pulse_ai/features/orchestrator/presentation/initialize_agent_submit_handler.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/initialize_agent_submit_payload.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_placeholder_feedback.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/cursor_integration_settings_sheet.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/initialize_agent_modal.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/orchestrator_app_top_bar.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/orchestrator_bottom_bar.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/orchestrator_breadcrumb_bar.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/orchestrator_empty_state_body.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/recent_projects_sidebar.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/workflow_prd_workspace.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/workflow_techspec_workspace.dart';
import 'package:pulse_ai/shared/theme/pulse_theme_data.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';

final class OrchestratorPage extends StatelessWidget {
  const OrchestratorPage({super.key});

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = PulseThemeData.build();
    return Theme(
      data: theme,
      child: BlocListener<ImportFlowCubit, ImportFlowState>(
        listenWhen: (ImportFlowState previous, ImportFlowState current) =>
            previous.status != current.status &&
            current.status != ImportFlowStatus.idle &&
            current.status != ImportFlowStatus.loading,
        listener: (BuildContext context, ImportFlowState state) {
          unawaited(
            ImportProjectFlowOutcomeHandler.handle(
              state: state,
              refreshRecentProjects: () =>
                  context.read<RecentProjectsCubit>().refresh(),
              showImportFailure: (String? failureMessage) =>
                  ImportProjectFeedback.showImportFailure(
                    context,
                    failureMessage: failureMessage,
                  ),
              resetImportFlow: () => context.read<ImportFlowCubit>().reset(),
            ),
          );
        },
        child:
            BlocBuilder<
              OrchestratorMainContentCubit,
              OrchestratorMainContentState
            >(
              builder:
                  (
                    BuildContext context,
                    OrchestratorMainContentState contentState,
                  ) {
                    final bool isWorkflowView =
                        contentState.view ==
                            OrchestratorMainContentView.prdWorkflow ||
                        contentState.view ==
                            OrchestratorMainContentView.techspecWorkflow;

                    return ColoredBox(
                      color: PulseColors.background,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: <Widget>[
                          _OrchestratorChrome(
                            onOpenCursorSettings: () {
                              _openCursorIntegrationSettings(context);
                            },
                          ),
                          const Expanded(child: _OrchestratorMainContent()),
                          if (!isWorkflowView) const OrchestratorBottomBar(),
                        ],
                      ),
                    );
                  },
            ),
      ),
    );
  }
}

void _openCursorIntegrationSettings(BuildContext context) {
  unawaited(showCursorIntegrationSettingsSheet(context));
}

final class _OrchestratorChrome extends StatelessWidget {
  const _OrchestratorChrome({required this.onOpenCursorSettings});

  final VoidCallback onOpenCursorSettings;

  @override
  Widget build(BuildContext context) {
    return OrchestratorAppTopBar(
      onImportProject: () {
        unawaited(
          Navigator.of(
            context,
          ).pushNamed<void>(RoutePaths.orchestratorImportSelectSource),
        );
      },
      onOpenCursorSettings: onOpenCursorSettings,
      onPlaceholder: () =>
          OrchestratorPlaceholderFeedback.showComingSoon(context),
    );
  }
}

final class _OrchestratorMainContent extends StatelessWidget {
  const _OrchestratorMainContent();

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<RecentProjectsCubit, RecentProjectsState>(
      builder: (BuildContext context, RecentProjectsState state) {
        final bool showSidebar = state.projects.isNotEmpty;

        return Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (showSidebar)
              RecentProjectsSidebar(
                onNewProject: () {
                  unawaited(_showInitializeAgentModal(context, state));
                },
              ),
            Expanded(
              child:
                  BlocBuilder<
                    OrchestratorMainContentCubit,
                    OrchestratorMainContentState
                  >(
                    builder:
                        (
                          BuildContext context,
                          OrchestratorMainContentState contentState,
                        ) {
                          final bool isWorkflowView =
                              contentState.view ==
                                  OrchestratorMainContentView.prdWorkflow ||
                              contentState.view ==
                                  OrchestratorMainContentView.techspecWorkflow;

                          return Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: <Widget>[
                              if (!isWorkflowView)
                                const OrchestratorBreadcrumbBar(),
                              const Expanded(
                                child: _OrchestratorScrollableBody(),
                              ),
                            ],
                          );
                        },
                  ),
            ),
          ],
        );
      },
    );
  }
}

Future<void> _showInitializeAgentModal(
  BuildContext context,
  RecentProjectsState projectsState,
) {
  final OrchestratorMainContentCubit mainContentCubit = context
      .read<OrchestratorMainContentCubit>();
  final RecentProjectsCubit recentProjectsCubit = context
      .read<RecentProjectsCubit>();
  final OrchestratorComposition composition = context
      .read<OrchestratorComposition>();

  return showInitializeAgentModal(
    context,
    projects: projectsState.projects,
    activeProjectId: projectsState.activeProjectId,
    onSubmit: (InitializeAgentSubmitPayload payload) {
      unawaited(
        InitializeAgentSubmitHandler.handle(
          context: context,
          mainContentCubit: mainContentCubit,
          recentProjectsCubit: recentProjectsCubit,
          createWorkflowUseCase: composition.createWorkflowUseCase,
          payload: payload,
        ),
      );
    },
  );
}

final class _OrchestratorScrollableBody extends StatelessWidget {
  const _OrchestratorScrollableBody();

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<RecentProjectsCubit, RecentProjectsState>(
      builder: (BuildContext context, RecentProjectsState projectsState) {
        return BlocBuilder<
          OrchestratorMainContentCubit,
          OrchestratorMainContentState
        >(
          builder:
              (
                BuildContext context,
                OrchestratorMainContentState contentState,
              ) {
                if (contentState.view ==
                    OrchestratorMainContentView.prdWorkflow) {
                  return _OrchestratorPrdBody(
                    contentState: contentState,
                    projectsState: projectsState,
                  );
                }

                if (contentState.view ==
                    OrchestratorMainContentView.techspecWorkflow) {
                  final PrdPhaseStatus prdPhaseStatus =
                      contentState.activeWorkflow?.prdPhaseStatus ??
                      PrdPhaseStatus.draft;

                  final String workflowSlug =
                      contentState.activeWorkflow?.slug ?? 'workflow';

                  return WorkflowTechspecWorkspace(
                    workflowSlug: workflowSlug,
                    prdPhaseStatus: prdPhaseStatus,
                    onInitialize: () =>
                        OrchestratorPlaceholderFeedback.showComingSoon(context),
                    onApplyInstruction: () =>
                        OrchestratorPlaceholderFeedback.showComingSoon(context),
                  );
                }

                return OrchestratorEmptyStateBody(
                  onSelectLocal: () {
                    final ImportFlowStatus status = context
                        .read<ImportFlowCubit>()
                        .state
                        .status;
                    if (status == ImportFlowStatus.loading) {
                      return;
                    }
                    unawaited(context.read<ImportFlowCubit>().importLocal());
                  },
                  onPlaceholder: () =>
                      OrchestratorPlaceholderFeedback.showComingSoon(context),
                );
              },
        );
      },
    );
  }
}

final class _OrchestratorPrdBody extends StatelessWidget {
  const _OrchestratorPrdBody({
    required this.contentState,
    required this.projectsState,
  });

  final OrchestratorMainContentState contentState;
  final RecentProjectsState projectsState;

  @override
  Widget build(BuildContext context) {
    final WorkflowEntity? workflow = contentState.activeWorkflow;
    if (workflow == null) {
      return OrchestratorEmptyStateBody(
        onSelectLocal: () {
          final ImportFlowStatus status = context
              .read<ImportFlowCubit>()
              .state
              .status;
          if (status == ImportFlowStatus.loading) {
            return;
          }
          unawaited(context.read<ImportFlowCubit>().importLocal());
        },
        onPlaceholder: () =>
            OrchestratorPlaceholderFeedback.showComingSoon(context),
      );
    }

    LocalProjectEntity? project;
    for (final LocalProjectEntity candidate in projectsState.projects) {
      if (candidate.id == workflow.projectId) {
        project = candidate;
        break;
      }
    }

    if (project == null) {
      return OrchestratorEmptyStateBody(
        onSelectLocal: () {
          final ImportFlowStatus status = context
              .read<ImportFlowCubit>()
              .state
              .status;
          if (status == ImportFlowStatus.loading) {
            return;
          }
          unawaited(context.read<ImportFlowCubit>().importLocal());
        },
        onPlaceholder: () =>
            OrchestratorPlaceholderFeedback.showComingSoon(context),
      );
    }

    return WorkflowPrdWorkspace(
      workflow: workflow,
      repoPath: project.canonicalPath,
      onOpenCursorSettings: () {
        _openCursorIntegrationSettings(context);
      },
    );
  }
}
