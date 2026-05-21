import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_key.dart';

final class WorkflowEntity {
  const WorkflowEntity({
    required this.projectId,
    required this.slug,
    required this.branchName,
    required this.prdPhaseStatus,
    required this.createdAt,
    this.directive,
  });

  final String projectId;
  final String slug;
  final String branchName;
  final String? directive;
  final PrdPhaseStatus prdPhaseStatus;
  final DateTime createdAt;

  String get workflowKey =>
      WorkflowKey.compose(projectId: projectId, slug: slug);

  WorkflowEntity copyWith({
    String? branchName,
    String? directive,
    PrdPhaseStatus? prdPhaseStatus,
  }) {
    return WorkflowEntity(
      projectId: projectId,
      slug: slug,
      branchName: branchName ?? this.branchName,
      directive: directive ?? this.directive,
      prdPhaseStatus: prdPhaseStatus ?? this.prdPhaseStatus,
      createdAt: createdAt,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        other is WorkflowEntity &&
            other.projectId == projectId &&
            other.slug == slug &&
            other.branchName == branchName &&
            other.directive == directive &&
            other.prdPhaseStatus == prdPhaseStatus &&
            other.createdAt == createdAt;
  }

  @override
  int get hashCode => Object.hash(
    projectId,
    slug,
    branchName,
    directive,
    prdPhaseStatus,
    createdAt,
  );
}
