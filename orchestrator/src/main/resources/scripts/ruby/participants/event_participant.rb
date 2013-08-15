class EventParticipant < Ruote::Participant

  MESSAGE = 'message'

  def do_not_thread
    true
  end

  def on_workitem
    begin

      raise 'message not set' unless workitem.params.has_key? 'message'
      raise 'host_id not set' unless workitem.params.has_key? 'host_id'
      message = workitem.params['message']
      host_id = workitem.params['host_id']
      workflow_name = workitem.wf_name

      $user_logger.debug("#{workflow_name}-#{host_id} - {}", message)

      reply(workitem)

    rescue Exception => e
      flunk(workitem, e)
    end
  end

end