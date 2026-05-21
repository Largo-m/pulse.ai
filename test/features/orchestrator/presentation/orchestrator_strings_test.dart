import 'package:flutter_test/flutter_test.dart';

import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';

void main() {
  group('OrchestratorStrings', () {
    test('exposes non-empty PT-BR copy for primary empty state', () {
      expect(OrchestratorStrings.emptyStateTitle, isNotEmpty);
      expect(OrchestratorStrings.emptyStateSubtitle, isNotEmpty);
      expect(OrchestratorStrings.emptyStateTitle, contains('Bem-vindo'));
    });

    test('exposes non-empty CTA labels for local and remote flows', () {
      expect(OrchestratorStrings.localProjectButton, isNotEmpty);
      expect(OrchestratorStrings.remoteProjectButton, isNotEmpty);
      expect(
        OrchestratorStrings.localProjectTitle,
        isNot(equals('Open Local Project')),
      );
    });

    test('comingSoonMessage is defined for placeholder feedback', () {
      expect(OrchestratorStrings.comingSoonMessage, isNotEmpty);
    });

    test('exposes non-empty PT-BR copy for recent projects sidebar', () {
      expect(OrchestratorStrings.recentProjectsSectionTitle, isNotEmpty);
      expect(
        OrchestratorStrings.recentProjectsSectionTitle,
        contains('Projetos recentes'),
      );
      expect(OrchestratorStrings.recentProjectNewButtonTooltip, isNotEmpty);
      expect(OrchestratorStrings.recentProjectSelectSemantics, isNotEmpty);
      expect(OrchestratorStrings.recentProjectActiveSemantics, isNotEmpty);
      expect(OrchestratorStrings.recentProjectExpandSemantics, isNotEmpty);
      expect(OrchestratorStrings.recentProjectCollapseSemantics, isNotEmpty);
    });

    test(
      'initialize agent modal copy is localized and exposes form labels',
      () {
        expect(OrchestratorStrings.initializeAgentModalTitle, isNotEmpty);
        expect(
          OrchestratorStrings.initializeAgentModalTitle,
          isNot(equals('Initialize New Agent')),
        );
        expect(
          OrchestratorStrings.initializeAgentCoreDirectiveLabel,
          isNotEmpty,
        );
        expect(OrchestratorStrings.initializeAgentNameLabel, isNotEmpty);
        expect(OrchestratorStrings.initializeAgentProjectLabel, isNotEmpty);
        expect(OrchestratorStrings.initializeAgentBranchLabel, isNotEmpty);
        expect(OrchestratorStrings.initializeAgentSubmitButton, isNotEmpty);
      },
    );

    test('initialize agent branch load states expose non-empty PT-BR copy', () {
      expect(OrchestratorStrings.initializeAgentBranchesLoading, isNotEmpty);
      expect(
        OrchestratorStrings.initializeAgentBranchesLoading,
        contains('Carregando'),
      );
      expect(
        OrchestratorStrings.initializeAgentBranchesLoading,
        isNot(equals('Loading branches…')),
      );
      expect(OrchestratorStrings.initializeAgentBranchesNotGit, isNotEmpty);
      expect(
        OrchestratorStrings.initializeAgentBranchesNotGit,
        contains('repositório Git'),
      );
      expect(OrchestratorStrings.initializeAgentBranchesLoadFailed, isNotEmpty);
      expect(
        OrchestratorStrings.initializeAgentBranchesLoadFailed,
        contains('carregar'),
      );
      expect(
        OrchestratorStrings.initializeAgentBranchesLoadingSemantics,
        isNotEmpty,
      );
      expect(
        OrchestratorStrings.initializeAgentBranchesNotGitSemantics,
        isNotEmpty,
      );
      expect(
        OrchestratorStrings.initializeAgentBranchesLoadFailedSemantics,
        isNotEmpty,
      );
      expect(
        OrchestratorStrings.initializeAgentBranchesPermissionDenied,
        isNotEmpty,
      );
      expect(
        OrchestratorStrings.initializeAgentBranchesPermissionDenied,
        contains('Reimporte'),
      );
      expect(
        OrchestratorStrings.initializeAgentBranchesPermissionDeniedSemantics,
        isNotEmpty,
      );
    });

    test('recent projects sidebar strings are not English placeholders', () {
      expect(
        OrchestratorStrings.recentProjectsSectionTitle,
        isNot(equals('Recent Projects')),
      );
      expect(
        OrchestratorStrings.recentProjectNewButtonTooltip,
        isNot(equals('New Agent')),
      );
    });

    test('cursor connection remediation copy is localized in PT-BR', () {
      expect(
        OrchestratorStrings.cursorConnectionMissingCredentialRemediation,
        isNotEmpty,
      );
      expect(
        OrchestratorStrings.cursorConnectionMissingCredentialRemediation,
        contains('Cursor'),
      );
      expect(
        OrchestratorStrings.cursorConnectionUnauthorizedRemediation,
        isNotEmpty,
      );
      expect(
        OrchestratorStrings.cursorConnectionUnauthorizedRemediation,
        contains('401'),
      );
      expect(
        OrchestratorStrings.cursorConnectionDisconnectedRemediation,
        isNotEmpty,
      );
      expect(OrchestratorStrings.cursorConnectionCheckingSemantics, isNotEmpty);
      expect(OrchestratorStrings.cursorConnectionBannerCta, isNotEmpty);
      expect(
        OrchestratorStrings.cursorConnectionBannerCta,
        contains('configura'),
      );
    });

    test('prd workflow stream and status copy is localized in PT-BR', () {
      expect(OrchestratorStrings.prdWorkflowStatusRunning, isNotEmpty);
      expect(
        OrchestratorStrings.prdWorkflowStatusRunning,
        contains('execução'),
      );
      expect(OrchestratorStrings.prdWorkflowStreamEmpty, isNotEmpty);
      expect(OrchestratorStrings.prdWorkflowCancelButton, isNotEmpty);
      expect(
        OrchestratorStrings.prdWorkflowUserActionRequiredTitle,
        isNotEmpty,
      );
      expect(OrchestratorStrings.prdWorkflowRunFailedGeneric, isNotEmpty);
      expect(OrchestratorStrings.prdWorkflowStreamUnavailable, isNotEmpty);
      expect(OrchestratorStrings.prdWorkflowStreamEventAssistant, isNotEmpty);
      expect(
        OrchestratorStrings.prdWorkflowStatusPendingApproval,
        isNot(equals('Pending approval')),
      );
    });

    test('prd review copy is localized in PT-BR', () {
      expect(OrchestratorStrings.prdReviewApproveButton, isNotEmpty);
      expect(
        OrchestratorStrings.prdReviewApproveButton,
        isNot(equals('Approve PRD')),
      );
      expect(OrchestratorStrings.prdReviewRejectButton, isNotEmpty);
      expect(OrchestratorStrings.prdReviewUnsavedOverwriteTitle, isNotEmpty);
      expect(OrchestratorStrings.prdReviewUserEditedBadge, isNotEmpty);
      expect(OrchestratorStrings.prdReviewUserEditedBadge, contains('usuário'));
      expect(OrchestratorStrings.prdReviewApproveSemantics, isNotEmpty);
      expect(OrchestratorStrings.prdReviewRejectSemantics, isNotEmpty);
    });

    test('workflow techspec initialization copy is localized in PT-BR', () {
      expect(OrchestratorStrings.workflowTechspecEmptyTitle, isNotEmpty);
      expect(
        OrchestratorStrings.workflowTechspecEmptyTitle,
        isNot(equals('No Technical Specification Yet')),
      );
      expect(OrchestratorStrings.workflowTechspecInitializeButton, isNotEmpty);
      expect(
        OrchestratorStrings.workflowTechspecInitializeButton,
        contains('techspec'),
      );
      expect(OrchestratorStrings.workflowTechspecPrdCompleteBanner, isNotEmpty);
      expect(OrchestratorStrings.workflowPhaseTechspec, isNotEmpty);
      expect(OrchestratorStrings.workflowTechspecApplyButton, isNotEmpty);
    });
  });
}
