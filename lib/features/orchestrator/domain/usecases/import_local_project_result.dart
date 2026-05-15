import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';

enum ImportLocalProjectOutcome { cancelled, success, failure }

final class ImportLocalProjectResult {
  const ImportLocalProjectResult(
    this.outcome, {
    this.project,
    this.failureMessage,
  });

  final ImportLocalProjectOutcome outcome;
  final LocalProjectEntity? project;
  final String? failureMessage;
}
