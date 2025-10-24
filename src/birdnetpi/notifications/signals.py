from blinker import Namespace

signals = Namespace()

detection_signal = signals.signal("detection")
detection_with_taxa_signal = signals.signal("detection_with_taxa")
