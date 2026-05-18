import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/shared/theme/pulse_typography.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';

final class WorkflowTechspecInstructionBar extends StatefulWidget {
  const WorkflowTechspecInstructionBar({super.key, required this.onApply});

  final VoidCallback onApply;

  @override
  State<WorkflowTechspecInstructionBar> createState() =>
      _WorkflowTechspecInstructionBarState();
}

final class _WorkflowTechspecInstructionBarState
    extends State<WorkflowTechspecInstructionBar> {
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
                hintText:
                    OrchestratorStrings.workflowTechspecInstructionPlaceholder,
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
                  Icons.add_comment_outlined,
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
                    label: OrchestratorStrings.workflowTechspecApplySemantics,
                    child: SizedBox(
                      height: PulseDimensions
                          .workflowInstructionBarApplyButtonHeight,
                      child: FilledButton(
                        onPressed: widget.onApply,
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
                          OrchestratorStrings.workflowTechspecApplyButton
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
