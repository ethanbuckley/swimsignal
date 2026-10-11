#!/bin/zsh
# queue.sh <jobs-file>: each line "name mode [table]"; runs run_variant.sh one at a time, skipping finished ones.
H=${0:A:h}
S=${DIAG_DIR:?set DIAG_DIR to a scratch folder}
while read -r name mode table; do
  [[ -z $name || $name == \#* ]] && continue
  [[ -f $S/logs/$name/done ]] && continue
  echo "$(date +%T) start $name"
  $H/run_variant.sh $name $mode $table
  echo "$(date +%T) end $name"
done < $1
echo all done
