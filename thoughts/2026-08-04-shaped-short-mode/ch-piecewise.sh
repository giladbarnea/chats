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
(( message_count >= 3 )) || {
    print -u2 "The piecewise curve needs at least three messages."
    exit 1
}

size_weight=1
pivot_index=$(( (message_count + 1) / 2 ))
left_steepness=2
right_steepness=2
minimum_short_length=50

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
            -v pivot_index="$pivot_index" \
            -v left_steepness="$left_steepness" \
            -v right_steepness="$right_steepness" \
            'BEGIN {
                if (message_index <= pivot_index) {
                    progress = (message_index - 1) / (pivot_index - 1)
                    position_factor = (1 - progress) ^ left_steepness
                } else {
                    progress = (message_index - pivot_index) / (message_count - pivot_index)
                    position_factor = 1 - (1 - progress) ^ right_steepness
                }

                size_factor = maximum_size ^ (1 - size_weight) * message_size ^ size_weight
                printf "%.0f", position_factor * size_factor
            }'
    )

    ch \
        "$session_id" \
        "$message_index" \
        --no-metadata \
        --short="$(( short_limit < minimum_short_length ? minimum_short_length : short_limit ))"
done
