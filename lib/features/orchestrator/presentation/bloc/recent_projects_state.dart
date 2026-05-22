import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';

final class RecentProjectsState {
  const RecentProjectsState({
    this.projects = const <LocalProjectEntity>[],
    this.activeProjectId,
    this.expandedProjectIds = const <String>[],
    this.workflowsByProjectId = const <String, List<WorkflowEntity>>{},
    this.isLoading = false,
  });

  final List<LocalProjectEntity> projects;
  final String? activeProjectId;
  final List<String> expandedProjectIds;
  final Map<String, List<WorkflowEntity>> workflowsByProjectId;
  final bool isLoading;

  List<WorkflowEntity> workflowsForProject(String projectId) {
    return workflowsByProjectId[projectId] ?? const <WorkflowEntity>[];
  }

  bool isProjectExpanded(String projectId) {
    return expandedProjectIds.contains(projectId);
  }

  RecentProjectsState copyWith({
    List<LocalProjectEntity>? projects,
    String? activeProjectId,
    bool clearActiveProjectId = false,
    List<String>? expandedProjectIds,
    Map<String, List<WorkflowEntity>>? workflowsByProjectId,
    bool? isLoading,
  }) {
    return RecentProjectsState(
      projects: projects ?? this.projects,
      activeProjectId: clearActiveProjectId
          ? null
          : activeProjectId ?? this.activeProjectId,
      expandedProjectIds: expandedProjectIds ?? this.expandedProjectIds,
      workflowsByProjectId: workflowsByProjectId ?? this.workflowsByProjectId,
      isLoading: isLoading ?? this.isLoading,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        other is RecentProjectsState &&
            other.isLoading == isLoading &&
            other.activeProjectId == activeProjectId &&
            _listEquals(other.projects, projects) &&
            _listEqualsStrings(other.expandedProjectIds, expandedProjectIds) &&
            _mapEquals(other.workflowsByProjectId, workflowsByProjectId);
  }

  @override
  int get hashCode => Object.hash(
    projects,
    activeProjectId,
    expandedProjectIds,
    workflowsByProjectId,
    isLoading,
  );

  bool _listEquals(
    List<LocalProjectEntity> left,
    List<LocalProjectEntity> right,
  ) {
    if (left.length != right.length) {
      return false;
    }
    for (int index = 0; index < left.length; index++) {
      if (left[index] != right[index]) {
        return false;
      }
    }
    return true;
  }

  bool _listEqualsStrings(List<String> left, List<String> right) {
    if (left.length != right.length) {
      return false;
    }
    for (int index = 0; index < left.length; index++) {
      if (left[index] != right[index]) {
        return false;
      }
    }
    return true;
  }

  bool _mapEquals(
    Map<String, List<WorkflowEntity>> left,
    Map<String, List<WorkflowEntity>> right,
  ) {
    if (left.length != right.length) {
      return false;
    }
    for (final MapEntry<String, List<WorkflowEntity>> entry in left.entries) {
      final List<WorkflowEntity>? otherList = right[entry.key];
      if (otherList == null || !_workflowListEquals(entry.value, otherList)) {
        return false;
      }
    }
    return true;
  }

  bool _workflowListEquals(
    List<WorkflowEntity> left,
    List<WorkflowEntity> right,
  ) {
    if (left.length != right.length) {
      return false;
    }
    for (int index = 0; index < left.length; index++) {
      if (left[index] != right[index]) {
        return false;
      }
    }
    return true;
  }
}
