/* Notification bell polling & dropdown */
(function() {
    var POLL_INTERVAL = 30000; // 30 seconds
    var bellList = document.getElementById('notifBellList');
    var bellCount = document.getElementById('notifBellCount');
    var bellDot = document.getElementById('notifDot');
    var bellMarkAll = document.getElementById('bellMarkAll');
    var sidebarBadge = document.getElementById('notifBadge');

    if (!bellList) return;

    function fetchUnread() {
        fetch('/notifications/api/unread', {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            updateBadge(data.unread_count);
            renderList(data.notifications);
        })
        .catch(function() {});
    }

    function updateBadge(count) {
        if (count > 0) {
            if (bellCount) {
                bellCount.textContent = count > 99 ? '99+' : count;
                bellCount.style.display = 'flex';
            }
            if (bellDot) bellDot.style.display = '';
            if (bellMarkAll) bellMarkAll.style.display = '';
            if (sidebarBadge) {
                sidebarBadge.textContent = count > 99 ? '99+' : count;
                sidebarBadge.style.display = '';
            }
        } else {
            if (bellCount) bellCount.style.display = 'none';
            if (bellDot) bellDot.style.display = 'none';
            if (bellMarkAll) bellMarkAll.style.display = 'none';
            if (sidebarBadge) sidebarBadge.style.display = 'none';
        }
    }

    function renderList(notifs) {
        if (!notifs || notifs.length === 0) {
            bellList.innerHTML = '<div style="padding:var(--space-4);text-align:center;color:var(--color-text-muted);font-size:var(--font-size-sm);">' +
                '<i class="bi bi-bell-slash" style="font-size:1.4rem;opacity:0.3;display:block;margin-bottom:var(--space-1);"></i>' +
                'No new notifications</div>';
            return;
        }
        var html = '';
        notifs.forEach(function(n) {
            var color = n.type_color || 'accent';
            html += '<a href="' + (n.action_url || '/notifications') + '" ' +
                'onclick="markReadBell(' + n.id + ')" ' +
                'style="display:flex;gap:var(--space-2);padding:var(--space-2) var(--space-3);border-bottom:1px solid var(--color-border);text-decoration:none;color:inherit;' +
                (n.is_read ? '' : 'background:var(--color-surface-raised);') + '">' +
                '<div style="width:28px;height:28px;border-radius:50%;background:var(--color-' + color + ');display:flex;align-items:center;justify-content:center;flex-shrink:0;">' +
                '<i class="bi ' + (n.category_icon || 'bi-bell') + '" style="color:#fff;font-size:0.75rem;"></i></div>' +
                '<div style="flex:1;min-width:0;">' +
                '<div style="font-size:var(--font-size-sm);font-weight:' + (n.is_read ? '400' : '600') + ';white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + n.title + '</div>' +
                '<div style="font-size:var(--font-size-xs);color:var(--color-text-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + (n.message || '').substring(0, 80) + '</div>' +
                '</div>' +
                '<span style="font-size:10px;color:var(--color-text-muted);white-space:nowrap;padding-top:2px;">' + (n.time_ago || '') + '</span>' +
                '</a>';
        });
        bellList.innerHTML = html;
    }

    window.markReadBell = function(id) {
        fetch('/notifications/' + id + '/read', {
            method: 'POST',
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        });
    };

    window.markAllReadBell = function() {
        fetch('/notifications/mark-all-read', {
            method: 'POST',
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        }).then(function(r) { return r.json(); }).then(function() {
            fetchUnread();
        });
    };

    // Initial fetch + polling
    fetchUnread();
    setInterval(fetchUnread, POLL_INTERVAL);
})();
