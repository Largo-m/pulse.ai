import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';

final class PrdReviewMarkdownEditor extends StatefulWidget {
  const PrdReviewMarkdownEditor({
    super.key,
    required this.textNotifier,
    required this.onChanged,
    required this.enabled,
    this.expandToParent = false,
  });

  final ValueNotifier<String> textNotifier;
  final ValueChanged<String> onChanged;
  final bool enabled;
  final bool expandToParent;

  @override
  State<PrdReviewMarkdownEditor> createState() =>
      _PrdReviewMarkdownEditorState();
}

final class _PrdReviewMarkdownEditorState
    extends State<PrdReviewMarkdownEditor> {
  late final TextEditingController _controller;
  bool _syncingFromNotifier = false;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.textNotifier.value);
    widget.textNotifier.addListener(_onExternalTextChanged);
    _controller.addListener(_onControllerChanged);
  }

  @override
  void didUpdateWidget(PrdReviewMarkdownEditor oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.textNotifier != widget.textNotifier) {
      oldWidget.textNotifier.removeListener(_onExternalTextChanged);
      widget.textNotifier.addListener(_onExternalTextChanged);
    }
    if (oldWidget.enabled != widget.enabled && !widget.enabled) {
      _controller.selection = TextSelection.collapsed(
        offset: _controller.text.length,
      );
    }
  }

  @override
  void dispose() {
    widget.textNotifier.removeListener(_onExternalTextChanged);
    _controller.removeListener(_onControllerChanged);
    _controller.dispose();
    super.dispose();
  }

  void _onExternalTextChanged() {
    final String next = widget.textNotifier.value;
    if (_controller.text == next) {
      return;
    }
    _syncingFromNotifier = true;
    _controller.value = TextEditingValue(
      text: next,
      selection: TextSelection.collapsed(offset: next.length),
    );
    _syncingFromNotifier = false;
  }

  void _onControllerChanged() {
    if (_syncingFromNotifier) {
      return;
    }
    widget.onChanged(_controller.text);
  }

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;

    return Semantics(
      label: OrchestratorStrings.prdReviewEditorSemantics,
      textField: true,
      child: Padding(
        padding: PulseInsets.prdReviewEditor,
        child: SizedBox(
          width: double.infinity,
          height: widget.expandToParent
              ? double.infinity
              : PulseDimensions.prdReviewEditorMinHeight,
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
              style: textTheme.bodyMedium?.copyWith(
                color: PulseColors.onSurface,
              ),
              decoration: const InputDecoration(
                border: InputBorder.none,
                enabledBorder: InputBorder.none,
                focusedBorder: InputBorder.none,
                contentPadding: EdgeInsets.all(
                  PulseDimensions.workflowInstructionBarOuterInset,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
