import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_artifact_presentation.dart';

void main() {
  group('prdArtifactFailureMessageForKey', () {
    test('maps missingArtifact key to PT-BR missing copy', () {
      expect(
        prdArtifactFailureMessageForKey(
          PrdArtifactFailureMessageKeys.missingArtifact,
        ),
        OrchestratorStrings.prdArtifactMissing,
      );
      expect(
        prdArtifactFailureMessageForKey(
          PrdArtifactFailureMessageKeys.missingArtifact,
        ),
        isNot(equals('missingArtifact')),
      );
    });
  });

  group('PrdArtifactPresentation', () {
    test(
      'showsRestoredRunOnPrdCard is true when sourceRunId matches restoredRunId',
      () {
        expect(
          PrdArtifactPresentation.showsRestoredRunOnPrdCard(
            sourceRunId: 'run-a',
            restoredRunId: 'run-a',
          ),
          isTrue,
        );
        expect(
          PrdArtifactPresentation.showsRestoredRunOnPrdCard(
            sourceRunId: 'run-a',
            restoredRunId: 'run-b',
          ),
          isFalse,
        );
        expect(
          PrdArtifactPresentation.showsRestoredRunOnPrdCard(
            sourceRunId: null,
            restoredRunId: 'run-a',
          ),
          isFalse,
        );
      },
    );

    test('restoredRunLabel includes run id in PT-BR', () {
      expect(
        PrdArtifactPresentation.restoredRunLabel('run-42'),
        OrchestratorStrings.prdArtifactRestoredRunLabel('run-42'),
      );
      expect(
        PrdArtifactPresentation.restoredRunLabel('run-42'),
        contains('run-42'),
      );
    });
  });
}
