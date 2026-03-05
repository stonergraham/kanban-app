// Card Detail Page JavaScript

const CARD_ID = parseInt(window.location.pathname.split('/card/')[1]);

// Checklist Functions
function showAddChecklistItem() {
    document.getElementById('addChecklistForm').style.display = 'block';
    document.getElementById('newChecklistText').focus();
}

function cancelAddChecklistItem() {
    document.getElementById('addChecklistForm').style.display = 'none';
    document.getElementById('newChecklistText').value = '';
}

function addChecklistItem(parentId = null, level = 0) {
    const text = document.getElementById('newChecklistText').value.trim();
    if (!text) return;
    
    const formData = new FormData();
    formData.append('text', text);
    if (parentId) formData.append('parent_id', parentId);
    formData.append('level', level);
    
    fetch(`/card/${CARD_ID}/checklist/add`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        } else {
            alert('Error: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error adding checklist item');
    });
}

function toggleChecklistItem(itemId) {
    fetch(`/checklist/${itemId}/toggle`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const text = document.getElementById(`checklist-text-${itemId}`);
            if (data.completed) {
                text.classList.add('completed');
            } else {
                text.classList.remove('completed');
            }
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

function editChecklistItemInline(itemId) {
    const textSpan = document.getElementById(`checklist-text-${itemId}`);
    const currentText = textSpan.textContent.trim();
    
    const input = document.createElement('input');
    input.type = 'text';
    input.value = currentText;
    input.className = 'checklist-edit-input';
    
    input.onblur = function() {
        saveChecklistEdit(itemId, input.value, textSpan);
    };
    
    input.onkeydown = function(e) {
        if (e.key === 'Enter') {
            saveChecklistEdit(itemId, input.value, textSpan);
        } else if (e.key === 'Escape') {
            textSpan.textContent = currentText;
            input.replaceWith(textSpan);
        }
    };
    
    textSpan.replaceWith(input);
    input.focus();
    input.select();
}

function saveChecklistEdit(itemId, newText, originalSpan) {
    if (!newText.trim()) {
        alert('Text cannot be empty');
        return;
    }
    
    const formData = new FormData();
    formData.append('text', newText);
    
    fetch(`/checklist/${itemId}/edit`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

function deleteChecklistItem(itemId) {
    if (!confirm('Delete this checklist item?')) return;
    
    fetch(`/checklist/${itemId}/delete`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

function indentChecklistItem(itemId, direction) {
    const formData = new FormData();
    formData.append('direction', direction);
    
    fetch(`/checklist/${itemId}/indent`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

// Comment Functions
function editComment(commentId) {
    const textDiv = document.getElementById(`comment-text-${commentId}`);
    const currentText = textDiv.textContent.trim();
    
    const textarea = document.createElement('textarea');
    textarea.value = currentText;
    textarea.className = 'comment-edit-textarea';
    textarea.rows = 3;
    
    const actions = document.createElement('div');
    actions.className = 'form-actions';
    actions.style.marginTop = '0.5rem';
    
    const saveBtn = document.createElement('button');
    saveBtn.textContent = 'Save';
    saveBtn.className = 'btn btn-sm btn-primary';
    saveBtn.onclick = function() {
        saveCommentEdit(commentId, textarea.value, textDiv);
    };
    
    const cancelBtn = document.createElement('button');
    cancelBtn.textContent = 'Cancel';
    cancelBtn.className = 'btn btn-sm btn-secondary';
    cancelBtn.onclick = function() {
        textDiv.textContent = currentText;
        textarea.remove();
        actions.remove();
    };
    
    actions.appendChild(saveBtn);
    actions.appendChild(cancelBtn);
    
    textDiv.textContent = '';
    textDiv.appendChild(textarea);
    textDiv.appendChild(actions);
    textarea.focus();
}

function saveCommentEdit(commentId, newText, originalDiv) {
    if (!newText.trim()) {
        alert('Comment cannot be empty');
        return;
    }
    
    const formData = new FormData();
    formData.append('text', newText);
    
    fetch(`/comment/${commentId}/edit`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error saving comment');
    });
}

console.log('Card detail page loaded');
