import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/orchestrator_main_content_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/orchestrator_main_content_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/recent_projects_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/recent_projects_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/recent_project_sidebar_workflows_mapper.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/recent_project_tree_node.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/ui/pulse_chrome_icon_button.dart';

final class RecentProjectsSidebar extends StatelessWidget {
  const RecentProjectsSidebar({super.key, required this.onNewProject});

  final VoidCallback onNewProject;

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<
      OrchestratorMainContentCubit,
      OrchestratorMainContentState
    >(
      builder:
          (BuildContext context, OrchestratorMainContentState contentState) {
            final String? activeSlug = contentState.activeWorkflow?.slug;

            return BlocBuilder<RecentProjectsCubit, RecentProjectsState>(
              builder: (BuildContext context, RecentProjectsState state) {
                return SizedBox(
                  width: PulseDimensions.orchestratorSidebarWidth,
                  child: ColoredBox(
                    color: PulseColors.surfaceContainer,
                    child: DecoratedBox(
                      decoration: const BoxDecoration(
                        border: Border(
                          right: BorderSide(color: PulseColors.outlineVariant),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: <Widget>[
                          _RecentProjectsSidebarHeader(
                            onNewProject: onNewProject,
                          ),
                          Expanded(
                            child: ListView.separated(
                              padding: PulseInsets.sidebarNav,
                              itemCount: state.projects.length,
                              separatorBuilder:
                                  (BuildContext context, int index) =>
                                      const SizedBox(
                                        height: PulseDimensions.sectionGapSm,
                                      ),
                              itemBuilder: (BuildContext context, int index) {
                                final LocalProjectEntity project =
                                    state.projects[index];
                                final bool isActive =
                                    project.id == state.activeProjectId;
                                final bool isExpanded = state.isProjectExpanded(
                                  project.id,
                                );

                                return Padding(
                                  padding: PulseInsets.sidebarTreeGroup,
                                  child: RecentProjectTreeNode(
                                    project: project,
                                    isActive: isActive,
                                    isExpanded: isExpanded,
                                    agents: mapWorkflowsToSidebarAgents(
                                      workflows: state.workflowsForProject(
                                        project.id,
                                      ),
                                      activeSlug:
                                          project.id == state.activeProjectId
                                          ? activeSlug
                                          : null,
                                    ),
                                    onSelected: () {
                                      unawaited(
                                        _selectProject(
                                          context,
                                          projectId: project.id,
                                        ),
                                      );
                                    },
                                    onAgentSelected: (String slug) {
                                      unawaited(
                                        _openWorkflow(
                                          context,
                                          projectId: project.id,
                                          slug: slug,
                                        ),
                                      );
                                    },
                                    onToggleExpanded: () {
                                      context
                                          .read<RecentProjectsCubit>()
                                          .toggleProjectExpanded(project.id);
                                    },
                                  ),
                                );
                              },
                            ),
                          ),
                          const DecoratedBox(
                            decoration: BoxDecoration(
                              border: Border(
                                top: BorderSide(
                                  color: PulseColors.outlineVariant,
                                ),
                              ),
                            ),
                            child: SizedBox(
                              height: PulseDimensions.sidebarHeaderPadding,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              },
            );
          },
    );
  }
}

Future<void> _selectProject(
  BuildContext context, {
  required String projectId,
}) async {
  await context.read<RecentProjectsCubit>().selectProject(projectId);
}

Future<void> _openWorkflow(
  BuildContext context, {
  required String projectId,
  required String slug,
}) async {
  final RecentProjectsState projectsState = context
      .read<RecentProjectsCubit>()
      .state;
  final List<WorkflowEntity> workflows = projectsState.workflowsForProject(
    projectId,
  );

  WorkflowEntity? workflow;
  for (final WorkflowEntity candidate in workflows) {
    if (candidate.slug == slug) {
      workflow = candidate;
      break;
    }
  }

  if (workflow == null) {
    return;
  }

  await context.read<RecentProjectsCubit>().selectProject(projectId);
  if (!context.mounted) {
    return;
  }

  context.read<OrchestratorMainContentCubit>().openWorkflowFromSidebar(
    workflow,
  );
}

final class _RecentProjectsSidebarHeader extends StatelessWidget {
  const _RecentProjectsSidebarHeader({required this.onNewProject});

  final VoidCallback onNewProject;

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;

    return DecoratedBox(
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: PulseColors.outlineVariant)),
      ),
      child: Padding(
        padding: PulseInsets.sidebarHeader,
        child: Row(
          children: <Widget>[
            Expanded(
              child: Text(
                OrchestratorStrings.recentProjectsSectionTitle.toUpperCase(),
                style: (textTheme.labelLarge ?? const TextStyle()).copyWith(
                  color: PulseColors.outline,
                  letterSpacing:
                      PulseDimensions.sidebarSectionTitleLetterSpacing,
                ),
              ),
            ),
            PulseChromeIconButton(
              icon: Icons.add,
              onPressed: onNewProject,
              tooltip: OrchestratorStrings.recentProjectNewButtonTooltip,
              semanticsLabel: OrchestratorStrings.recentProjectNewButtonTooltip,
              iconSize: PulseDimensions.sidebarAddButtonIconSize,
              showBorderOnHover: true,
            ),
          ],
        ),
      ),
    );
  }
}
