#!/usr/bin/env -S FORCE_OMZ=1 zsh -i
set -euo pipefail

(( $# == 1 )) || {
    print -u2 "Usage: ${0:t} SESSION_ID"
    exit 64
}

session_id=$1
message_count=$(ch "$session_id" -l | yq '.messages')
[[ "$message_count" == <-> ]] || {
    print -u2 "Could not get a numeric message count for session $session_id."
    exit 1
}
(( message_count >= 1 )) || {
    print -u2 "Session $session_id has no messages."
    exit 1
}

size_weight=1
position_weight=1

typeset -a message_sizes
maximum_size=0

for (( message_index = 1; message_index <= message_count; message_index++ )); do
    message_size=$(ch "$session_id" "$message_index" --no-metadata | wc -c)
    message_sizes[$message_index]=$message_size
    maximum_size=$(( message_size > maximum_size ? message_size : maximum_size ))
done

for (( message_index = 1; message_index <= message_count; message_index++ )); do
    short_limit=$(
        awk \
            -v message_index="$message_index" \
            -v message_count="$message_count" \
            -v message_size="${message_sizes[$message_index]}" \
            -v maximum_size="$maximum_size" \
            -v size_weight="$size_weight" \
            -v position_weight="$position_weight" \
            'BEGIN {
                position = message_index / message_count
                position_factor = position ^ position_weight
                size_factor = maximum_size ^ (1 - size_weight) * message_size ^ size_weight
                printf "%.0f", position_factor * size_factor
            }'
    )

    ch "$session_id" "$message_index" --no-metadata --short="$((short_limit < 8 ? 8 : short_limit))"
done
