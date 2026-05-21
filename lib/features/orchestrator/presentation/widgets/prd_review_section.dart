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
import 'package:pulse_ai/features/orchestrator/presentation/widgets/prd_review_action_bar.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/prd_review_feedback_bar.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/prd_review_markdown_editor.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/prd_review_repo_context_header.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/prd_review_unsaved_overwrite_dialog.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';

final class PrdReviewSection extends StatelessWidget {
  const PrdReviewSection({super.key});

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
      child: BlocBuilder<PrdReviewCubit, PrdReviewState>(
        builder: (BuildContext context, PrdReviewState state) {
          final PrdReviewCubit cubit = context.read<PrdReviewCubit>();
          final TextTheme textTheme = Theme.of(context).textTheme;
          final bool showFeedback =
              state.loadStatus == PrdReviewLoadStatus.ready &&
              !state.isApproved;

          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              PrdReviewRepoContextHeader(
                repoPath: state.repoPathHeader,
                branchName: state.branchNameHeader,
              ),
              Expanded(
                child: PrdReviewMarkdownEditor(
                  textNotifier: cubit.editorText,
                  onChanged: cubit.onEditorTextChanged,
                  enabled: state.isEditable,
                ),
              ),
              if (state.failureMessageKey != null)
                Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal:
                        PulseDimensions.workflowInstructionBarOuterInset,
                    vertical: PulseDimensions.sectionGapSm,
                  ),
                  child: Text(
                    state.failureMessageKey!,
                    style: textTheme.bodySmall?.copyWith(
                      color: PulseColors.secondary,
                    ),
                  ),
                ),
              if (state.approveBlockedMessageKey != null)
                Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal:
                        PulseDimensions.workflowInstructionBarOuterInset,
                    vertical: PulseDimensions.sectionGapSm,
                  ),
                  child: Text(
                    state.approveBlockedMessageKey!,
                    style: textTheme.bodySmall?.copyWith(
                      color: PulseColors.onSurfaceVariant,
                    ),
                  ),
                ),
              PrdReviewActionBar(
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
              if (showFeedback)
                PrdReviewFeedbackBar(
                  enabled: state.canReject && !state.isRejecting,
                  onSubmit: (String feedback) =>
                      unawaited(cubit.rejectWithFeedback(feedback)),
                ),
            ],
          );
        },
      ),
    );
  }
}
