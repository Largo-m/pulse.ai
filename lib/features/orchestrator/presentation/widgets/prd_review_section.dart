import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_review_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_review_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_workflow_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_workflow_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_review_load_status.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_workflow_phase_ui_status.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_artifact_presentation.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/prd_artifact_card.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/prd_review_action_bar.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/prd_review_feedback_bar.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/prd_review_markdown_editor.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/prd_review_unsaved_overwrite_dialog.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/workflow_section_header.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';

final class PrdReviewSection extends StatelessWidget {
  const PrdReviewSection({super.key, required this.workflowSlug});

  final String workflowSlug;

  @override
  Widget build(BuildContext context) {
    return MultiBlocListener(
      listeners: <BlocListener<dynamic, dynamic>>[
        BlocListener<CursorConnectionCubit, CursorConnectionState>(
          listener: (BuildContext context, CursorConnectionState state) {
            context.read<PrdReviewCubit>().syncConnectionGate(state);
          },
        ),
        BlocListener<PrdWorkflowCubit, PrdWorkflowState>(
          listenWhen: (PrdWorkflowState previous, PrdWorkflowState current) =>
              previous.phaseStatus != current.phaseStatus,
          listener: (BuildContext context, PrdWorkflowState state) {
            if (state.phaseStatus == PrdWorkflowPhaseUiStatus.pendingApproval) {
              unawaited(context.read<PrdReviewCubit>().loadDraft());
            }
          },
        ),
        BlocListener<PrdReviewCubit, PrdReviewState>(
          listenWhen: (PrdReviewState previous, PrdReviewState current) =>
              !previous.mustConfirmOverwrite && current.mustConfirmOverwrite,
          listener: (BuildContext context, PrdReviewState state) async {
            final bool? confirmed = await PrdReviewUnsavedOverwriteDialog.show(
              context,
            );
            if (!context.mounted) {
              return;
            }
            final PrdReviewCubit cubit = context.read<PrdReviewCubit>();
            if (confirmed == true) {
              cubit.confirmOverwriteIncomingDraft();
            } else {
              cubit.cancelOverwriteIncomingDraft();
            }
          },
        ),
      ],
      child: BlocBuilder<PrdWorkflowCubit, PrdWorkflowState>(
        builder: (BuildContext context, PrdWorkflowState workflowState) {
          return BlocBuilder<PrdReviewCubit, PrdReviewState>(
            builder: (BuildContext context, PrdReviewState state) {
              final PrdReviewCubit cubit = context.read<PrdReviewCubit>();
              final TextTheme textTheme = Theme.of(context).textTheme;
              final bool showFeedback =
                  state.loadStatus == PrdReviewLoadStatus.ready &&
                  !state.isApproved;
              final bool showArtifact =
                  state.loadStatus == PrdReviewLoadStatus.ready ||
                  state.loadStatus == PrdReviewLoadStatus.loading;
              final bool isMissingArtifact =
                  state.failureMessageKey ==
                  PrdArtifactFailureMessageKeys.missingArtifact;
              final String? artifactStatusMessage =
                  state.failureMessageKey == null
                  ? null
                  : prdArtifactFailureMessageForKey(state.failureMessageKey!);
              final String? runSubtitle =
                  PrdArtifactPresentation.showsRestoredRunOnPrdCard(
                    sourceRunId: state.sourceRunId,
                    restoredRunId: workflowState.restoredRunId,
                  )
                  ? PrdArtifactPresentation.restoredRunLabel(state.sourceRunId!)
                  : null;

              if (!showArtifact) {
                return const SizedBox.shrink();
              }

              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: <Widget>[
                  const WorkflowSectionHeader(
                    icon: Icons.description_outlined,
                    title: OrchestratorStrings.prdArtifactDraftedMessage,
                  ),
                  const SizedBox(height: PulseDimensions.sectionGapMd),
                  PrdArtifactCard(
                    fileName: OrchestratorStrings.prdArtifactFileName(
                      workflowSlug,
                    ),
                    subtitle: runSubtitle,
                    footer: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: <Widget>[
                        if (artifactStatusMessage != null && !isMissingArtifact)
                          Padding(
                            padding: const EdgeInsets.only(
                              bottom: PulseDimensions.sectionGapSm,
                            ),
                            child: Text(
                              artifactStatusMessage,
                              style: textTheme.bodySmall?.copyWith(
                                color: PulseColors.secondary,
                              ),
                            ),
                          ),
                        if (state.approveBlockedMessageKey != null)
                          Padding(
                            padding: const EdgeInsets.only(
                              bottom: PulseDimensions.sectionGapSm,
                            ),
                            child: Text(
                              state.approveBlockedMessageKey!,
                              style: textTheme.bodySmall?.copyWith(
                                color: PulseColors.onSurfaceVariant,
                              ),
                            ),
                          ),
                        PrdReviewActionBar(
                          artifactMode: true,
                          showsUserEditedBadge: state.showsUserEditedBadge,
                          canSave: state.canSave,
                          canApprove: state.canApprove,
                          canReject: state.canReject,
                          isSaving: state.isSaving,
                          isApproving: state.isApproving,
                          isRejecting: state.isRejecting,
                          onSave: () => unawaited(cubit.saveDraft()),
                          onApprove: () => unawaited(cubit.approve()),
                          onReject: () {},
                        ),
                      ],
                    ),
                    child: isMissingArtifact
                        ? Padding(
                            padding: PulseInsets.prdArtifactTitleBar,
                            child: Align(
                              alignment: Alignment.topLeft,
                              child: Text(
                                artifactStatusMessage!,
                                style: textTheme.bodyMedium?.copyWith(
                                  color: PulseColors.onSurfaceVariant,
                                ),
                              ),
                            ),
                          )
                        : PrdReviewMarkdownEditor(
                            textNotifier: cubit.editorText,
                            onChanged: cubit.onEditorTextChanged,
                            enabled: state.isEditable,
                            expandToParent: true,
                          ),
                  ),
                  if (showFeedback)
                    PrdReviewFeedbackBar(
                      enabled: state.canReject && !state.isRejecting,
                      onSubmit: (String feedback) =>
                          unawaited(cubit.rejectWithFeedback(feedback)),
                    ),
                ],
              );
            },
          );
        },
      ),
    );
  }
}
