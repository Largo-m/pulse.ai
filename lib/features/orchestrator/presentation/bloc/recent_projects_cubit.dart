import 'dart:async';

import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_recent_projects_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/select_active_project_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/recent_projects_state.dart';

final class RecentProjectsCubit extends Cubit<RecentProjectsState> {
  RecentProjectsCubit({
    required ListRecentProjectsUseCase listRecentProjectsUseCase,
    required SelectActiveProjectUseCase selectActiveProjectUseCase,
    bool loadOnCreate = true,
  }) : _listRecentProjectsUseCase = listRecentProjectsUseCase,
       _selectActiveProjectUseCase = selectActiveProjectUseCase,
       super(
         loadOnCreate
             ? const RecentProjectsState(isLoading: true)
             : const RecentProjectsState(),
       ) {
    if (loadOnCreate) {
      unawaited(refresh());
    }
  }

  final ListRecentProjectsUseCase _listRecentProjectsUseCase;
  final SelectActiveProjectUseCase _selectActiveProjectUseCase;

  Future<void> selectProject(String projectId) async {
    await _selectActiveProjectUseCase.select(projectId);
    emit(state.copyWith(activeProjectId: projectId));
  }

  Future<void> refresh() async {
    emit(state.copyWith(isLoading: true));

    await _selectActiveProjectUseCase.reconcileActiveWithRecentProjects();

    final List<LocalProjectEntity> projects =
        await _listRecentProjectsUseCase();
    final String? activeProjectId = await _selectActiveProjectUseCase
        .readActiveProjectId();

    emit(
      RecentProjectsState(
        projects: projects,
        activeProjectId: _activeIdWhenKnown(projects, activeProjectId),
        isLoading: false,
      ),
    );
  }

  String? _activeIdWhenKnown(
    List<LocalProjectEntity> projects,
    String? activeProjectId,
  ) {
    if (activeProjectId == null) {
      return null;
    }

    final bool isKnown = projects.any(
      (LocalProjectEntity project) => project.id == activeProjectId,
    );

    return isKnown ? activeProjectId : null;
  }
}
