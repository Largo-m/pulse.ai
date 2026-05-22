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
        expect(OrchestratorStrings.initializeAgentSlugLabel, isNotEmpty);
        expect(OrchestratorStrings.initializeAgentSlugHint, isNotEmpty);
        expect(
          OrchestratorStrings.initializeAgentSlugRequiredError,
          isNotEmpty,
        );
        expect(
          OrchestratorStrings.initializeAgentSlugInvalidFormatError,
          isNotEmpty,
        );
        expect(OrchestratorStrings.initializeAgentSubmitButton, isNotEmpty);
      },
    );

    test('techspec PRD gate copy is localized PT-BR', () {
      expect(OrchestratorStrings.workflowTechspecPrdRequiredTitle, isNotEmpty);
      expect(
        OrchestratorStrings.workflowTechspecPrdRequiredTitle,
        contains('PRD'),
      );
      expect(
        OrchestratorStrings.workflowTechspecPrdRequiredSubtitle,
        isNotEmpty,
      );
    });

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

    test('cursor settings modal copy is localized in PT-BR', () {
      expect(OrchestratorStrings.cursorSettingsModalTitle, isNotEmpty);
      expect(OrchestratorStrings.cursorSettingsModalTitle, contains('Cursor'));
      expect(OrchestratorStrings.cursorSettingsApiKeyLabel, isNotEmpty);
      expect(OrchestratorStrings.cursorSettingsApiKeyHint, isNotEmpty);
      expect(OrchestratorStrings.cursorSettingsHelperText, isNotEmpty);
      expect(OrchestratorStrings.cursorSettingsConfiguredStatus, isNotEmpty);
      expect(
        OrchestratorStrings.cursorSettingsConfiguredStatus,
        contains('configurada'),
      );
      expect(OrchestratorStrings.cursorSettingsTestButton, isNotEmpty);
      expect(OrchestratorStrings.cursorSettingsTestButton, contains('Testar'));
      expect(OrchestratorStrings.cursorSettingsSaveButton, isNotEmpty);
      expect(OrchestratorStrings.cursorSettingsRemoveButton, isNotEmpty);
      expect(OrchestratorStrings.cursorSettingsDocumentationUrl, isNotEmpty);
      expect(
        OrchestratorStrings.cursorSettingsDocumentationUrl,
        startsWith('https://'),
      );
      expect(
        OrchestratorStrings.cursorSettingsDocumentationLinkLabel,
        isNotEmpty,
      );
      expect(
        OrchestratorStrings.cursorSettingsDocumentationLinkLabel,
        isNot(equals('Cursor documentation')),
      );
      expect(OrchestratorStrings.cursorSettingsRemoveConfirmTitle, isNotEmpty);
      expect(OrchestratorStrings.cursorSettingsRemoveConfirmBody, isNotEmpty);
      expect(OrchestratorStrings.cursorSettingsRemoveConfirmButton, isNotEmpty);
      expect(OrchestratorStrings.cursorSettingsRemoveCancelButton, isNotEmpty);
      expect(OrchestratorStrings.cursorSettingsCloseSemantics, isNotEmpty);
      expect(OrchestratorStrings.cursorSettingsTestSuccessFeedback, isNotEmpty);
      expect(
        OrchestratorStrings.cursorSettingsTestSuccessFeedback,
        contains('salvar'),
      );
      expect(OrchestratorStrings.cursorSettingsSaveFailedFeedback, isNotEmpty);
    });

    test('cursor settings feedback copy is localized in PT-BR', () {
      expect(
        OrchestratorStrings.cursorSettingsSaveBlockedWithoutTest,
        isNotEmpty,
      );
      expect(
        OrchestratorStrings.cursorSettingsSaveBlockedWithoutTest,
        contains('Teste'),
      );
      expect(
        OrchestratorStrings.cursorSettingsUnauthorizedFeedback,
        isNotEmpty,
      );
      expect(
        OrchestratorStrings.cursorSettingsUnauthorizedFeedback,
        contains('401'),
      );
      expect(
        OrchestratorStrings.cursorSettingsMissingCredentialFeedback,
        isNotEmpty,
      );
      expect(OrchestratorStrings.cursorSettingsNetworkFeedback, isNotEmpty);
      expect(OrchestratorStrings.cursorSettingsUnknownFeedback, isNotEmpty);
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

    test('workspace feed copy is localized in PT-BR', () {
      expect(OrchestratorStrings.prdWorkflowSystemProcessingTitle, isNotEmpty);
      expect(
        OrchestratorStrings.prdWorkflowSystemProcessingTitle,
        contains('PROCESSAMENTO'),
      );
      expect(OrchestratorStrings.prdArtifactApproveButton, isNotEmpty);
      expect(
        OrchestratorStrings.prdArtifactApproveButton,
        contains('artefato'),
      );
      expect(OrchestratorStrings.workflowArchiveTitle, isNotEmpty);
      expect(OrchestratorStrings.workflowTechspecMappingTitle, isNotEmpty);
      expect(
        OrchestratorStrings.prdArtifactFileName('meu-agente'),
        contains('meu-agente'),
      );
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
