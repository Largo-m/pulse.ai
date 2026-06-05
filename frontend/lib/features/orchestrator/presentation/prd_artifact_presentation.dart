import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';

abstract final class PrdArtifactFailureMessageKeys {
  static const String missingArtifact = 'missingArtifact';
  static const String adrListLoadFailed = 'adrListLoadFailed';
}

String prdArtifactFailureMessageForKey(String key) {
  return switch (key) {
    PrdArtifactFailureMessageKeys.missingArtifact =>
      OrchestratorStrings.prdArtifactMissing,
    PrdArtifactFailureMessageKeys.adrListLoadFailed =>
      OrchestratorStrings.prdAdrListLoadFailed,
    _ => OrchestratorStrings.prdReviewLoadFailed,
  };
}

final class PrdArtifactPresentation {
  const PrdArtifactPresentation._();

  static bool showsRestoredRunOnPrdCard({
    required String? sourceRunId,
    required String? restoredRunId,
  }) {
    if (sourceRunId == null || restoredRunId == null) {
      return false;
    }
    return sourceRunId == restoredRunId;
  }

  static String restoredRunLabel(String runId) {
    return OrchestratorStrings.prdArtifactRestoredRunLabel(runId);
  }
}
