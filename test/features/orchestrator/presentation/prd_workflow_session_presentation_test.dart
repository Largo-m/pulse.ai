import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_workflow_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_conversation_message_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_session_view_mode.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_stream_line_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_workflow_session_presentation.dart';

void main() {
  group('prdWorkflowFailureMessageForKey', () {
    test('maps restoreFailed key to PT-BR session restore message', () {
      expect(
        prdWorkflowFailureMessageForKey(
          PrdWorkflowFailureMessageKeys.restoreFailed,
        ),
        OrchestratorStrings.prdWorkflowSessionRestoreFailed,
      );
      expect(
        prdWorkflowFailureMessageForKey(
          PrdWorkflowFailureMessageKeys.restoreFailed,
        ),
        isNot(equals('restoreFailed')),
      );
    });

    test('maps unknown key to generic run failure message', () {
      expect(
        prdWorkflowFailureMessageForKey('unknown'),
        OrchestratorStrings.prdWorkflowRunFailedGeneric,
      );
    });
  });

  group('PrdWorkflowSessionPresentation', () {
    test('terminalLinesFor returns stream lines only when restored', () {
      const PrdStreamLineUiModel line = PrdStreamLineUiModel(
        sequence: 1,
        eventType: 'assistant',
        displayText: 'log',
      );
      const PrdWorkflowState restored = PrdWorkflowState(
        sessionViewMode: PrdSessionViewMode.restored,
        streamLines: <PrdStreamLineUiModel>[line],
      );

      expect(
        PrdWorkflowSessionPresentation.terminalLinesFor(restored),
        hasLength(1),
      );
      expect(
        PrdWorkflowSessionPresentation.terminalLinesFor(
          const PrdWorkflowState(
            sessionViewMode: PrdSessionViewMode.inProgressOnly,
            streamLines: <PrdStreamLineUiModel>[line],
          ),
        ),
        isEmpty,
      );
    });

    test(
      'terminalEmptyMessageFor distinguishes empty and in-progress modes',
      () {
        expect(
          PrdWorkflowSessionPresentation.terminalEmptyMessageFor(
            const PrdWorkflowState(sessionViewMode: PrdSessionViewMode.empty),
          ),
          OrchestratorStrings.prdWorkflowSessionEmptyBody,
        );
        expect(
          PrdWorkflowSessionPresentation.terminalEmptyMessageFor(
            const PrdWorkflowState(
              sessionViewMode: PrdSessionViewMode.inProgressOnly,
            ),
          ),
          OrchestratorStrings.prdWorkflowSessionInProgressBody,
        );
        expect(
          PrdWorkflowSessionPresentation.terminalEmptyMessageFor(
            const PrdWorkflowState(
              sessionViewMode: PrdSessionViewMode.restoreFailed,
            ),
          ),
          OrchestratorStrings.prdWorkflowSessionRestoreTerminalHint,
        );
      },
    );

    test('showsRestoreFailurePanel only for restoreFailed mode', () {
      expect(
        PrdWorkflowSessionPresentation.showsRestoreFailurePanel(
          const PrdWorkflowState(
            sessionViewMode: PrdSessionViewMode.restoreFailed,
          ),
        ),
        isTrue,
      );
      expect(
        PrdWorkflowSessionPresentation.showsRestoreFailurePanel(
          const PrdWorkflowState(sessionViewMode: PrdSessionViewMode.empty),
        ),
        isFalse,
      );
    });

    test('showsDirectiveBubble hides bubble when conversation is restored', () {
      final PrdConversationMessageUiModel message =
          PrdConversationMessageUiModel(
            role: PrdConversationMessageRole.user,
            displayText: 'directive',
            timestamp: DateTime.utc(2026, 5, 22),
            sequence: 1,
          );

      expect(
        PrdWorkflowSessionPresentation.showsDirectiveBubble(
          hasDirective: true,
          state: PrdWorkflowState(
            sessionViewMode: PrdSessionViewMode.restored,
            restoredConversationMessages: <PrdConversationMessageUiModel>[
              message,
            ],
          ),
        ),
        isFalse,
      );
      expect(
        PrdWorkflowSessionPresentation.showsDirectiveBubble(
          hasDirective: true,
          state: const PrdWorkflowState(
            sessionViewMode: PrdSessionViewMode.empty,
          ),
        ),
        isTrue,
      );
    });
  });
}
