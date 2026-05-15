import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';

enum ImportFlowStatus { idle, loading, success, cancelled, failure }

final class ImportFlowState {
  const ImportFlowState({
    this.status = ImportFlowStatus.idle,
    this.project,
    this.failureMessage,
  });

  final ImportFlowStatus status;
  final LocalProjectEntity? project;
  final String? failureMessage;

  ImportFlowState copyWith({
    ImportFlowStatus? status,
    LocalProjectEntity? project,
    String? failureMessage,
    bool clearProject = false,
    bool clearFailureMessage = false,
  }) {
    return ImportFlowState(
      status: status ?? this.status,
      project: clearProject ? null : project ?? this.project,
      failureMessage: clearFailureMessage
          ? null
          : failureMessage ?? this.failureMessage,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        other is ImportFlowState &&
            other.status == status &&
            other.project == project &&
            other.failureMessage == failureMessage;
  }

  @override
  int get hashCode => Object.hash(status, project, failureMessage);
}
