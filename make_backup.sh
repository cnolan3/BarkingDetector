tar -cf - ./recordings ./barking_detector.db -P | pv -s $(du -sb ./recordings | awk '{print $1}') | gzip > ./recording_backups/$(date +%Y%m%d-%H%M%S).tar.gz
