import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/shared/theme/pulse_typography.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';

final class PrdReviewFeedbackBar extends StatefulWidget {
  const PrdReviewFeedbackBar({
    super.key,
    required this.onSubmit,
    required this.enabled,
  });

  final ValueChanged<String> onSubmit;
  final bool enabled;

  @override
  State<PrdReviewFeedbackBar> createState() => _PrdReviewFeedbackBarState();
}

final class _PrdReviewFeedbackBarState extends State<PrdReviewFeedbackBar> {
  late final TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _submit() {
    final String feedback = _controller.text.trim();
    if (feedback.isEmpty || !widget.enabled) {
      return;
    }
    widget.onSubmit(feedback);
    _controller.clear();
  }

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;

    return DecoratedBox(
      decoration: const BoxDecoration(
        color: PulseColors.surfaceContainerLow,
        border: Border(top: BorderSide(color: PulseColors.outlineVariant)),
      ),
      child: Padding(
        padding: PulseInsets.workflowInstructionBarOuter,
        child: SizedBox(
          width: double.infinity,
          height: PulseDimensions.workflowInstructionBarFieldHeight,
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: PulseColors.background,
              borderRadius: BorderRadius.circular(
                PulseRadii.workflowInstructionBar,
              ),
              border: Border.all(color: PulseColors.outlineVariant),
            ),
            child: TextField(
              controller: _controller,
              enabled: widget.enabled,
              maxLines: null,
              expands: true,
              textAlignVertical: TextAlignVertical.center,
              style: textTheme.bodyMedium?.copyWith(
                color: PulseColors.onSurface,
              ),
              decoration: InputDecoration(
                isDense: true,
                border: InputBorder.none,
                enabledBorder: InputBorder.none,
                focusedBorder: InputBorder.none,
                hintText: OrchestratorStrings.prdReviewFeedbackPlaceholder,
                hintStyle: textTheme.bodyMedium?.copyWith(
                  color: PulseColors.outline.withValues(
                    alpha: PulseDimensions.workflowInstructionBarHintOpacity,
                  ),
                ),
                contentPadding: const EdgeInsets.symmetric(
                  vertical: PulseDimensions
                      .workflowInstructionBarFieldVerticalPadding,
                ),
                prefixIcon: const Icon(
                  Icons.rate_review_outlined,
                  size: PulseDimensions.workflowInstructionBarIconSize,
                  color: PulseColors.outline,
                ),
                prefixIconConstraints: const BoxConstraints(
                  minWidth: PulseDimensions.workflowInstructionBarPrefixWidth,
                  minHeight: PulseDimensions.workflowInstructionBarFieldHeight,
                ),
                suffixIcon: Padding(
                  padding: PulseInsets.workflowInstructionBarSuffix,
                  child: Semantics(
                    button: true,
                    enabled: widget.enabled,
                    label: OrchestratorStrings.prdReviewFeedbackSubmitSemantics,
                    child: SizedBox(
                      height: PulseDimensions
                          .workflowInstructionBarApplyButtonHeight,
                      child: FilledButton(
                        onPressed: widget.enabled ? _submit : null,
                        style: FilledButton.styleFrom(
                          backgroundColor: PulseColors.primaryContainer,
                          foregroundColor: PulseColors.onPrimaryContainer,
                          padding: PulseInsets
                              .workflowInstructionBarApplyButtonHorizontal,
                          minimumSize: const Size(
                            PulseDimensions
                                .workflowInstructionBarSuffixMinWidth,
                            PulseDimensions
                                .workflowInstructionBarApplyButtonHeight,
                          ),
                          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(
                              PulseRadii.workflowInstructionBar,
                            ),
                          ),
                          textStyle: context.pulseCtaButtonLabel(),
                        ),
                        child: Text(
                          OrchestratorStrings.prdReviewFeedbackSubmitButton
                              .toUpperCase(),
                        ),
                      ),
                    ),
                  ),
                ),
                suffixIconConstraints: const BoxConstraints(
                  minWidth:
                      PulseDimensions.workflowInstructionBarSuffixMinWidth,
                  minHeight:
                      PulseDimensions.workflowInstructionBarSuffixMinHeight,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
