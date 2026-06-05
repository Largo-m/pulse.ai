import 'package:pulse_ai/features/orchestrator/domain/entities/prd_session_snapshot.dart';

enum RestorePrdSessionOutcome { empty, inProgressOnly, restored }

final class RestorePrdSessionResult {
  const RestorePrdSessionResult({required this.outcome, this.snapshot});

  final RestorePrdSessionOutcome outcome;
  final PrdSessionSnapshot? snapshot;
}
