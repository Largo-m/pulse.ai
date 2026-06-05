import 'package:flutter/material.dart';

final class MouseHoverBuilder extends StatefulWidget {
  const MouseHoverBuilder({
    super.key,
    required this.builder,
    this.cursor = SystemMouseCursors.click,
  });

  final Widget Function(BuildContext context, bool isHovered) builder;
  final MouseCursor cursor;

  @override
  State<MouseHoverBuilder> createState() => _MouseHoverBuilderState();
}

class _MouseHoverBuilderState extends State<MouseHoverBuilder> {
  late final ValueNotifier<bool> _isHovered;

  @override
  void initState() {
    super.initState();
    _isHovered = ValueNotifier<bool>(false);
  }

  @override
  void dispose() {
    _isHovered.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onEnter: (_) => _isHovered.value = true,
      onExit: (_) => _isHovered.value = false,
      cursor: widget.cursor,
      child: ValueListenableBuilder<bool>(
        valueListenable: _isHovered,
        builder: (BuildContext context, bool isHovered, Widget? child) {
          return widget.builder(context, isHovered);
        },
      ),
    );
  }
}
