import 'dart:async';

import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_recent_projects_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_workflows_by_project_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/select_active_project_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/recent_projects_state.dart';

final class RecentProjectsCubit extends Cubit<RecentProjectsState> {
  RecentProjectsCubit({
    required ListRecentProjectsUseCase listRecentProjectsUseCase,
    required SelectActiveProjectUseCase selectActiveProjectUseCase,
    ListWorkflowsByProjectUseCase? listWorkflowsByProjectUseCase,
    bool loadOnCreate = true,
  }) : _listRecentProjectsUseCase = listRecentProjectsUseCase,
       _selectActiveProjectUseCase = selectActiveProjectUseCase,
       _listWorkflowsByProjectUseCase = listWorkflowsByProjectUseCase,
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
  final ListWorkflowsByProjectUseCase? _listWorkflowsByProjectUseCase;

  Future<void> selectProject(String projectId) async {
    await _selectActiveProjectUseCase.select(projectId);
    emit(
      state.copyWith(
        activeProjectId: projectId,
        expandedProjectIds: _expandedWithProject(projectId),
      ),
    );
  }

  void toggleProjectExpanded(String projectId) {
    final Set<String> expanded = state.expandedProjectIds.toSet();
    if (expanded.contains(projectId)) {
      expanded.remove(projectId);
    } else {
      expanded.add(projectId);
    }
    emit(state.copyWith(expandedProjectIds: expanded.toList()));
  }

  Future<void> refresh() async {
    emit(state.copyWith(isLoading: true));

    await _selectActiveProjectUseCase.reconcileActiveWithRecentProjects();

    final List<LocalProjectEntity> projects =
        await _listRecentProjectsUseCase();
    final String? activeProjectId = await _selectActiveProjectUseCase
        .readActiveProjectId();

    final String? knownActiveId = _activeIdWhenKnown(projects, activeProjectId);
    final Map<String, List<WorkflowEntity>> workflowsByProjectId =
        await _loadWorkflowsByProject(projects);

    emit(
      RecentProjectsState(
        projects: projects,
        activeProjectId: knownActiveId,
        expandedProjectIds: _expandedAfterRefresh(
          projects: projects,
          previousExpandedIds: state.expandedProjectIds,
          activeProjectId: knownActiveId,
        ),
        workflowsByProjectId: workflowsByProjectId,
        isLoading: false,
      ),
    );
  }

  Future<Map<String, List<WorkflowEntity>>> _loadWorkflowsByProject(
    List<LocalProjectEntity> projects,
  ) async {
    final ListWorkflowsByProjectUseCase? listUseCase =
        _listWorkflowsByProjectUseCase;
    if (listUseCase == null) {
      return const <String, List<WorkflowEntity>>{};
    }

    final Map<String, List<WorkflowEntity>> workflowsByProjectId =
        <String, List<WorkflowEntity>>{};
    for (final LocalProjectEntity project in projects) {
      final Either<Failure, List<WorkflowEntity>> result = await listUseCase(
        project.id,
      );
      workflowsByProjectId[project.id] = result.fold(
        (_) => const <WorkflowEntity>[],
        (List<WorkflowEntity> workflows) => workflows,
      );
    }
    return workflowsByProjectId;
  }

  List<String> _expandedWithProject(String projectId) {
    final Set<String> expanded = state.expandedProjectIds.toSet()
      ..add(projectId);
    return expanded.toList();
  }

  List<String> _expandedAfterRefresh({
    required List<LocalProjectEntity> projects,
    required List<String> previousExpandedIds,
    required String? activeProjectId,
  }) {
    final Set<String> knownIds = projects
        .map((LocalProjectEntity project) => project.id)
        .toSet();
    final Set<String> expanded = previousExpandedIds
        .where(knownIds.contains)
        .toSet();
    if (activeProjectId != null) {
      expanded.add(activeProjectId);
    }
    return expanded.toList();
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
