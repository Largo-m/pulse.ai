import 'package:flutter/material.dart';

final class WorkflowPreservingText extends StatelessWidget {
  const WorkflowPreservingText({super.key, required this.text, this.style});

  final String text;
  final TextStyle? style;

  @override
  Widget build(BuildContext context) {
    return SelectableText(
      text,
      style: style,
      maxLines: null,
      scrollPhysics: const NeverScrollableScrollPhysics(),
    );
  }
}
