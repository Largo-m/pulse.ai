import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/recent_projects_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/recent_projects_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/recent_project_list_tile.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';

final class RecentProjectsSidebar extends StatelessWidget {
  const RecentProjectsSidebar({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<RecentProjectsCubit, RecentProjectsState>(
      builder: (BuildContext context, RecentProjectsState state) {
        return SizedBox(
          width: PulseDimensions.orchestratorSidebarWidth,
          child: ColoredBox(
            color: PulseColors.surfaceContainerLowest,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Padding(
                  padding: PulseInsets.breadcrumbHorizontal.copyWith(
                    top: PulseDimensions.sectionGapMd,
                    bottom: PulseDimensions.sectionGapSm,
                  ),
                  child: Text(
                    OrchestratorStrings.recentProjectsSectionTitle,
                    style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      color: PulseColors.onSurfaceVariant,
                    ),
                  ),
                ),
                Expanded(
                  child: ListView.separated(
                    padding: const EdgeInsets.only(
                      left: PulseDimensions.horizontalInset,
                      right: PulseDimensions.horizontalInset,
                      bottom: PulseDimensions.sectionGapMd,
                    ),
                    itemCount: state.projects.length,
                    separatorBuilder: (BuildContext context, int index) =>
                        const SizedBox(height: PulseDimensions.sectionGapSm),
                    itemBuilder: (BuildContext context, int index) {
                      final LocalProjectEntity project = state.projects[index];
                      final bool isActive = project.id == state.activeProjectId;

                      return RecentProjectListTile(
                        project: project,
                        isActive: isActive,
                        onSelected: () {
                          unawaited(
                            context.read<RecentProjectsCubit>().selectProject(
                              project.id,
                            ),
                          );
                        },
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
