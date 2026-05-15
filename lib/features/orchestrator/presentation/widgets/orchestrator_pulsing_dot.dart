import 'package:flutter/material.dart';

import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';

final class OrchestratorPulsingDot extends StatefulWidget {
  const OrchestratorPulsingDot({super.key});

  @override
  State<OrchestratorPulsingDot> createState() => _OrchestratorPulsingDotState();
}

class _OrchestratorPulsingDotState extends State<OrchestratorPulsingDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: PulseDimensions.pulsingDurationMs),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: Tween<double>(
        begin: PulseDimensions.pulsingOpacityLow,
        end: PulseDimensions.pulsingOpacityHigh,
      ).animate(CurvedAnimation(parent: _controller, curve: Curves.easeInOut)),
      child: const SizedBox(
        width: PulseDimensions.standbyDotSize,
        height: PulseDimensions.standbyDotSize,
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: PulseColors.tertiary,
            shape: BoxShape.circle,
          ),
        ),
      ),
    );
  }
}
